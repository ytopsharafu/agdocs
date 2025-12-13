from collections import defaultdict
import re
from typing import Dict, List, Sequence

import frappe
from frappe.utils import (
    cint,
    cstr,
    escape_html,
    formatdate,
    get_link_to_form,
    getdate,
    nowdate,
    now_datetime,
)

try:
    from frappe.core.doctype.sms_settings.sms_settings import send_sms as _sms_send
except Exception:  # pragma: no cover - fallback for unexpected import issues
    _sms_send = None


@frappe.whitelist()
def send_test_email():
    """Send a quick test email using the admin/CC recipients."""
    settings = frappe.get_single("Document Alert Settings")
    recipients = _get_admin_emails(settings)

    if not recipients:
        frappe.throw("No email recipients found. Add Admin or CC email first.")

    subject = "Test Email - Document Alert System"
    message = """
        <p>This is a test email from the Document Alert System.</p>
        <p>If you received this, your email configuration is working.</p>
    """

    frappe.sendmail(recipients=recipients, subject=subject, message=message)
    return "Test email sent successfully."


@frappe.whitelist()
def send_test_sms():
    """Send a quick test SMS using the admin/CC mobile numbers."""
    settings = frappe.get_single("Document Alert Settings")
    sms_error = _get_sms_configuration_error()
    if sms_error:
        frappe.throw(sms_error)

    mobile_numbers = _get_admin_mobiles(settings)

    if not mobile_numbers:
        frappe.throw("No mobile numbers found. Add Admin or CC mobile first.")

    msg = "Test SMS from Document Alert System."

    if settings.sms_signature:
        msg += f" {settings.sms_signature}"

    _send_sms_message(mobile_numbers, msg, success_msg=False)
    return "Test SMS sent successfully."


def send_expiry_notifications():
    """Entry point for the scheduler: notify customers/employees about expiring docs."""
    log_context = _init_alert_log_context()

    try:
        settings = frappe.get_single("Document Alert Settings")
        if not settings.enable_email and not settings.enable_sms:
            frappe.logger().info("Document alerts skipped: both email and SMS are disabled.")
            log_context["status"] = "Skipped"
            log_context["failure_details"].append("Both email and SMS alerts are disabled.")
            _create_alert_log(log_context)
            return

        today = getdate(nowdate())
        bundles: List[Dict] = []
        bundles.extend(_build_customer_bundles(today))
        bundles.extend(_build_employee_bundles(today))

        if not bundles:
            frappe.logger().info("Document alerts: no expiring documents found.")
            log_context["status"] = "Skipped"
            log_context["failure_details"].append("No expiring documents matched the alert window.")
            _create_alert_log(log_context)
            return

        email_count = 0
        sms_count = 0
        email_failures = 0
        sms_failures = 0
        failure_details = log_context["failure_details"]
        log_context["total_records"] = len(bundles)

        admin_recipients = _get_admin_emails(settings)
        consolidate_admin_email = (
            settings.enable_email
            and cint(settings.get("consolidate_admin_email"))
            and bool(admin_recipients)
        )
        admin_digest_entries: List[Dict] = []

        for bundle in bundles:
            # make sure the latest admin contacts are attached before sending
            if settings.enable_email:
                if consolidate_admin_email:
                    admin_digest_entries.append(_clone_bundle_for_digest(bundle))
                else:
                    bundle["email_recipients"].update(admin_recipients)
            if settings.enable_sms:
                bundle["sms_recipients"].update(_get_admin_mobiles(settings))

            email_recipients = sorted(bundle["email_recipients"])
            sms_recipients = sorted(bundle["sms_recipients"])

            if settings.enable_email and email_recipients:
                log_context["email_attempts"] += 1
                try:
                    if _send_email_alert(bundle, recipients=email_recipients):
                        email_count += 1
                        _record_alert_detail(
                            log_context,
                            "Email",
                            email_recipients,
                            bundle,
                            "Sent",
                        )
                except Exception as exc:
                    email_failures += 1
                    _capture_alert_failure(
                        failure_details,
                        "Email",
                        bundle,
                        exc,
                        "Document Alert Email Failure",
                    )
                    _record_alert_detail(
                        log_context,
                        "Email",
                        email_recipients,
                        bundle,
                        "Failed",
                        cstr(exc),
                    )

            if settings.enable_sms and sms_recipients:
                log_context["sms_attempts"] += 1
                try:
                    if _send_sms_alert(bundle, settings, recipients=sms_recipients):
                        sms_count += 1
                        _record_alert_detail(
                            log_context,
                            "SMS",
                            sms_recipients,
                            bundle,
                            "Sent",
                        )
                except Exception as exc:
                    sms_failures += 1
                    _capture_alert_failure(
                        failure_details,
                        "SMS",
                        bundle,
                        exc,
                        "Document Alert SMS Failure",
                    )
                    _record_alert_detail(
                        log_context,
                        "SMS",
                        sms_recipients,
                        bundle,
                        "Failed",
                        cstr(exc),
                    )

        if consolidate_admin_email and admin_digest_entries:
            log_context["email_attempts"] += 1
            try:
                if _send_admin_digest_email(admin_recipients, admin_digest_entries):
                    email_count += 1
                    _record_alert_detail(
                        log_context,
                        "Email",
                        admin_recipients,
                        {"title": "Admin Summary", "parent": "Document Alert Settings"},
                        "Sent",
                    )
            except Exception as exc:
                email_failures += 1
                _capture_alert_failure(
                    failure_details,
                    "Email",
                    {"title": "Admin Summary"},
                    exc,
                    "Document Alert Admin Digest Failure",
                )
                _record_alert_detail(
                    log_context,
                    "Email",
                    admin_recipients,
                    {"title": "Admin Summary"},
                    "Failed",
                    cstr(exc),
                )

        log_context["emails_sent"] = email_count
        log_context["sms_sent"] = sms_count
        log_context["emails_failed"] = email_failures
        log_context["sms_failed"] = sms_failures

        derived_email_pending = max(
            log_context["email_attempts"] - email_count - email_failures,
            0,
        )
        log_context["email_queue_pending"] = max(
            _count_pending_email_queue(),
            derived_email_pending,
        )
        log_context["sms_pending"] = max(
            log_context["sms_attempts"] - sms_count - sms_failures,
            0,
        )

        frappe.logger().info(
            "Document alerts: %s email(s) and %s SMS alert(s) sent for %s record(s).",
            email_count,
            sms_count,
            len(bundles),
        )

        _create_alert_log(log_context)

    except Exception as err:
        log_context["status"] = "Failed"
        log_context["failure_details"].append(cstr(err))
        frappe.log_error(frappe.get_traceback(), "Document Alert Scheduler Failure")
        _create_alert_log(log_context)
        raise


def _build_customer_bundles(today):
    rows = frappe.db.sql(
        """
        select
            parent.name as parent,
            parent.customer,
            parent.customer_name,
            parent.customer_email,
            parent.customer_mobile,
            parent.extra_email,
            parent.extra_mobile,
            parent.enable_email_alert,
            parent.enable_sms_alert,
            child.name as rowname,
            child.document_type,
            child.document_number,
            child.alert_repeat_interval,
            dt.document_name,
            child.expiry_date,
            child.alert_days,
            child.notes,
            dt.alert_days as default_alert_days,
            dt.repeat_interval as default_repeat_interval
        from `tabCustomer Document Registration` parent
        inner join `tabDocument Detail` child
            on child.parent = parent.name
            and child.parenttype = 'Customer Document Registration'
            and child.parentfield = 'document_details'
        left join `tabDocument Type Master` dt
            on dt.name = child.document_type
        where parent.docstatus < 2
            and parent.active = 1
            and child.expiry_date is not null
        """,
        as_dict=True,
    )

    return _aggregate_rows(
        rows=rows,
        parenttype="Customer Document Registration",
        title_fn=lambda d: d.customer_name or d.customer or d.parent,
        email_flag="enable_email_alert",
        sms_flag="enable_sms_alert",
        email_fields=("customer_email", "extra_email"),
        sms_fields=("customer_mobile", "extra_mobile"),
        today=today,
    )


def _build_employee_bundles(today):
    rows = frappe.db.sql(
        """
        select
            parent.name as parent,
            parent.full_name,
            parent.customer_name,
            parent.email_id,
            parent.mobile_number,
            parent.extra_email,
            parent.extra_mobile,
            parent.notify_employee_email,
            parent.notify_employee_sms,
            cdr.customer_email as customer_alert_email,
            cdr.extra_email as customer_alert_extra_email,
            cdr.customer_mobile as customer_alert_mobile,
            cdr.extra_mobile as customer_alert_extra_mobile,
            case
                when ifnull(cdr.enable_email_alert, 0) = 1
                    and ifnull(cdr.employee_email_alert, 0) = 1
                then 1
                else 0
            end as customer_employee_email_allowed,
            case
                when ifnull(cdr.enable_sms_alert, 0) = 1
                    and ifnull(cdr.employee_sms_alert, 0) = 1
                then 1
                else 0
            end as customer_employee_sms_allowed,
            child.name as rowname,
            child.document_type,
            child.document_number,
            child.alert_repeat_interval,
            dt.document_name,
            child.expiry_date,
            child.alert_days,
            child.notes,
            dt.alert_days as default_alert_days,
            dt.repeat_interval as default_repeat_interval
        from `tabCustomer Employee Registration` parent
        inner join `tabDocument Detail` child
            on child.parent = parent.name
            and child.parenttype = 'Customer Employee Registration'
            and child.parentfield = 'document_details'
        left join `tabDocument Type Master` dt
            on dt.name = child.document_type
        left join `tabCustomer Document Registration` cdr
            on cdr.customer = parent.customer_name
        where parent.docstatus < 2
            and parent.active = 1
            and child.expiry_date is not null
        """,
        as_dict=True,
    )

    # The scheduler already injects admin contacts, so only include employee contacts
    return _aggregate_rows(
        rows=rows,
        parenttype="Customer Employee Registration",
        title_fn=lambda d: d.full_name or d.customer_name or d.parent,
        email_flag="notify_employee_email",
        sms_flag="notify_employee_sms",
        email_fields=("email_id", "extra_email"),
        sms_fields=("mobile_number", "extra_mobile"),
        today=today,
        extra_email_sources=(
            (
                "customer_employee_email_allowed",
                ("customer_alert_email", "customer_alert_extra_email"),
            ),
        ),
        extra_sms_sources=(
            (
                "customer_employee_sms_allowed",
                ("customer_alert_mobile", "customer_alert_extra_mobile"),
            ),
        ),
    )


def _aggregate_rows(
    rows: Sequence[Dict],
    parenttype: str,
    title_fn,
    email_flag: str,
    sms_flag: str,
    email_fields: Sequence[str],
    sms_fields: Sequence[str],
    today,
    extra_email_sources: Sequence = None,
    extra_sms_sources: Sequence = None,
):
    grouped = defaultdict(
        lambda: {
            "parent": None,
            "parenttype": parenttype,
            "title": "",
            "documents": [],
            "email_recipients": set(),
            "sms_recipients": set(),
            "allow_email": False,
            "allow_sms": False,
        }
    )

    for row in rows:
        entry = _prepare_document_entry(row, today)
        if not entry:
            continue

        bundle = grouped[row.parent]
        if not bundle["parent"]:
            bundle["parent"] = row.parent
            bundle["title"] = title_fn(row) or row.parent
            if row.get("customer_name"):
                bundle["customer_name"] = row.get("customer_name")

        bundle["documents"].append(entry)

        email_sources = []
        if email_flag:
            email_sources.append((email_flag, email_fields))
        if extra_email_sources:
            email_sources.extend(extra_email_sources)

        for flag, fields in email_sources:
            if flag and row.get(flag):
                bundle["allow_email"] = True
                bundle["email_recipients"].update(_collect_row_contacts(row, fields))

        sms_sources = []
        if sms_flag:
            sms_sources.append((sms_flag, sms_fields))
        if extra_sms_sources:
            sms_sources.extend(extra_sms_sources)

        for flag, fields in sms_sources:
            if flag and row.get(flag):
                bundle["allow_sms"] = True
                bundle["sms_recipients"].update(_collect_row_contacts(row, fields))

    bundles = []
    for bundle in grouped.values():
        if not bundle["documents"]:
            continue

        bundle["documents"].sort(key=lambda d: d["days_left"])
        bundle["email_recipients"] = set(filter(None, bundle["email_recipients"]))
        bundle["sms_recipients"] = set(filter(None, bundle["sms_recipients"]))
        bundles.append(bundle)

    return bundles


def _prepare_document_entry(row, today):
    if not row.get("expiry_date"):
        return None

    alert_days = cint(row.get("alert_days") or row.get("default_alert_days") or 0)
    if alert_days <= 0:
        return None

    expiry = getdate(row.get("expiry_date"))
    days_left = (expiry - today).days
    if days_left < 0 or days_left > alert_days:
        return None

    repeat_interval = cint(
        row.get("alert_repeat_interval")
        or row.get("default_repeat_interval")
        or 1
    )
    if repeat_interval <= 0:
        repeat_interval = 1

    window_age = alert_days - days_left
    if window_age % repeat_interval != 0:
        return None

    document_label = (
        row.get("document_name")
        or row.get("document_type")
        or "Document"
    )

    return {
        "document_type": document_label,
        "document_number": row.get("document_number") or "",
        "expiry_date": expiry,
        "days_left": days_left,
        "notes": row.get("notes") or "",
    }


def _send_email_alert(bundle, recipients=None):
    recipients = sorted(recipients or bundle["email_recipients"])
    if not recipients:
        return False

    subject = f"Document Expiry Alert - {bundle['title']}"
    message = _render_email_body(bundle)

    frappe.sendmail(recipients=recipients, subject=subject, message=message)
    return True


def _clone_bundle_for_digest(bundle):
    digest_bundle = {
        "parent": bundle["parent"],
        "parenttype": bundle["parenttype"],
        "title": bundle["title"],
        "customer_name": bundle.get("customer_name"),
        "documents": [doc.copy() for doc in bundle["documents"]],
    }
    return digest_bundle


def _send_admin_digest_email(recipients, bundles):
    recipients = sorted(recipients or [])
    if not recipients or not bundles:
        return False

    subject = f"Document Expiry Summary - {formatdate(nowdate())}"
    message = _render_admin_digest_body(bundles)
    frappe.sendmail(recipients=recipients, subject=subject, message=message)
    return True


def _render_admin_digest_body(bundles):
    sections = []
    for bundle in bundles:
        sections.append(
            f"""
            <div style="margin-bottom:18px;">
                <h3 style="margin:0 0 6px 0;">{escape_html(bundle['title'])}</h3>
                {_render_email_body(bundle, include_intro=False)}
            </div>
            """
        )

    return f"""
        <p>The following document alerts were generated on {formatdate(nowdate())}:</p>
        {''.join(sections)}
    """


def _render_email_body(bundle, include_intro=True):
    link = get_link_to_form(bundle["parenttype"], bundle["parent"])
    rows_html = []
    customer_line = ""
    if bundle.get("customer_name") and bundle.get("parenttype") == "Customer Employee Registration":
        customer_line = f"<p>Customer: <strong>{escape_html(bundle['customer_name'])}</strong></p>"

    for doc in bundle["documents"]:
        note = escape_html(doc["notes"]) if doc["notes"] else ""
        rows_html.append(
            f"""
            <tr>
                <td>{escape_html(doc["document_type"])}</td>
                <td>{escape_html(doc["document_number"])}</td>
                <td>{formatdate(doc["expiry_date"])}</td>
                <td>{_days_label(doc["days_left"])}</td>
                <td>{note}</td>
            </tr>
            """
        )

    table = (
        """
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <thead>
                <tr>
                    <th>Document</th>
                    <th>Document Number</th>
                    <th>Expiry Date</th>
                    <th>Due In</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
        """
        + "".join(rows_html)
        + """
            </tbody>
        </table>
        """
    )

    intro = ""
    if include_intro:
        intro = f"<p>The following document(s) for <strong>{escape_html(bundle['title'])}</strong> are due soon:</p>"

    return f"""
        {intro}
        {customer_line}
        {table}
        <p>Record: {link}</p>
    """


def _send_sms_alert(bundle, settings, recipients=None):
    recipients = sorted(recipients or bundle["sms_recipients"])
    if not recipients:
        return False

    doc_bits = []
    for doc in bundle["documents"]:
        doc_bits.append(
            f"{doc['document_type']} ({formatdate(doc['expiry_date'], 'dd-MMM')})"
        )

    sms = f"{bundle['title']} doc alert: " + "; ".join(doc_bits)
    if settings.sms_signature:
        sms = f"{sms} {settings.sms_signature}"

    _send_sms_message(recipients, sms)
    return True


def _days_label(days):
    if days == 0:
        return "Today"
    if days == 1:
        return "1 day"
    return f"{days} days"


def _collect_row_contacts(row, fields: Sequence[str]):
    values = []
    for field in fields:
        value = row.get(field)
        if value:
            values.append(cstr(value).strip())
    return [v for v in values if v]


def _get_admin_emails(settings):
    return _collect_contacts(settings.default_admin_email, settings.cc_emails)


def _get_admin_mobiles(settings):
    return _collect_contacts(settings.default_admin_mobile, settings.cc_mobiles)


def _collect_contacts(*parts):
    recipients: List[str] = []
    seen = set()

    for part in parts:
        if not part:
            continue

        if isinstance(part, (list, tuple, set)):
            tokens = part
        else:
            tokens = re.split(r"[,\n]+", cstr(part))

        for token in tokens:
            cleaned = token.strip()
            if cleaned and cleaned not in seen:
                recipients.append(cleaned)
                seen.add(cleaned)

    return recipients


def _get_sms_configuration_error():
    """Return a human friendly message if SMS Settings are incomplete."""
    required_fields = {
        "sms_gateway_url": "SMS Gateway URL",
        "message_parameter": "Message Parameter",
        "receiver_parameter": "Receiver Parameter",
    }

    try:
        values = frappe.db.get_value(
            "SMS Settings",
            "SMS Settings",
            list(required_fields.keys()),
            as_dict=True,
        )
    except frappe.DoesNotExistError:
        values = None

    if not values:
        return "SMS Settings are not configured. Update SMS Settings before testing."

    missing = [label for field, label in required_fields.items() if not cstr(values.get(field)).strip()]
    if missing:
        if len(missing) == 1:
            return f"SMS Settings is missing: {missing[0]}"
        return "SMS Settings is missing: " + ", ".join(missing)

    return ""


def _send_sms_message(recipients, msg, success_msg=True):
    """Compatibility wrapper so we support both frappe.send_sms and the DocType helper."""
    if hasattr(frappe, "send_sms"):
        return frappe.send_sms(recipients=recipients, msg=msg, success_msg=success_msg)

    if _sms_send:
        return _sms_send(receiver_list=recipients, msg=msg, success_msg=success_msg)

    frappe.throw("SMS sending is not available because frappe.send_sms is missing.")


def _init_alert_log_context():
    return {
        "status": "",
        "total_records": 0,
        "emails_sent": 0,
        "sms_sent": 0,
        "emails_failed": 0,
        "sms_failed": 0,
        "email_attempts": 0,
        "sms_attempts": 0,
        "email_queue_pending": 0,
        "sms_pending": 0,
        "failure_details": [],
        "details": [],
    }


def _capture_alert_failure(collector, channel, bundle, exc, title):
    label = f"{bundle.get('title') or bundle.get('parent')} ({bundle.get('parenttype')})"
    collector.append(f"{channel}: {label} -> {cstr(exc)}")
    frappe.log_error(frappe.get_traceback(), title)


def _record_alert_detail(context, channel, recipients, bundle, status, error_message=""):
    if not recipients:
        return

    template = {
        "channel": channel,
        "status": status,
        "error_message": error_message,
        "reference_doctype": bundle.get("parenttype"),
        "reference_name": bundle.get("parent"),
        "reference_title": bundle.get("title"),
    }

    for recipient in recipients:
        row = template.copy()
        row["recipient"] = recipient
        context["details"].append(row)


def _count_pending_email_queue():
    try:
        return frappe.db.count("Email Queue", {"status": "Not Sent"})
    except Exception:
        return 0


def _derive_alert_status(context):
    explicit = context.get("status")
    if explicit:
        return explicit

    successes = (context.get("emails_sent", 0) or 0) + (context.get("sms_sent", 0) or 0)
    failures = (context.get("emails_failed", 0) or 0) + (context.get("sms_failed", 0) or 0)

    if failures and not successes:
        return "Failed"
    if failures and successes:
        return "Partial Failures"
    if not successes:
        return "Skipped"
    return "Success"


def _create_alert_log(context):
    details = "\n".join(context.get("failure_details") or [])
    detail_rows = []
    for detail in context.get("details") or []:
        detail_rows.append(
            {
                "doctype": "Document Alert Log Detail",
                "channel": detail.get("channel"),
                "recipient": detail.get("recipient"),
                "status": detail.get("status"),
                "reference_doctype": detail.get("reference_doctype"),
                "reference_name": detail.get("reference_name"),
                "reference_title": detail.get("reference_title"),
                "error_message": detail.get("error_message"),
            }
        )

    payload = {
        "doctype": "Document Alert Log",
        "log_time": now_datetime(),
        "status": _derive_alert_status(context),
        "total_records": context.get("total_records", 0),
        "emails_sent": context.get("emails_sent", 0),
        "sms_sent": context.get("sms_sent", 0),
        "emails_failed": context.get("emails_failed", 0),
        "sms_failed": context.get("sms_failed", 0),
        "email_queue_pending": context.get("email_queue_pending", 0),
        "sms_pending": context.get("sms_pending", 0),
        "failure_details": details,
    }

    if detail_rows:
        payload["log_entries"] = detail_rows

    try:
        doc = frappe.get_doc(payload)
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Failed to insert Document Alert Log")
