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
)


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

    frappe.send_sms(recipients=mobile_numbers, msg=msg, success_msg=False)
    return "Test SMS sent successfully."


def send_expiry_notifications():
    """Entry point for the scheduler: notify customers/employees about expiring docs."""
    settings = frappe.get_single("Document Alert Settings")
    if not settings.enable_email and not settings.enable_sms:
        frappe.logger().info("Document alerts skipped: both email and SMS are disabled.")
        return

    today = getdate(nowdate())
    bundles: List[Dict] = []
    bundles.extend(_build_customer_bundles(today))
    bundles.extend(_build_employee_bundles(today))

    if not bundles:
        frappe.logger().info("Document alerts: no expiring documents found.")
        return

    email_count = 0
    sms_count = 0

    for bundle in bundles:
        # make sure the latest admin contacts are attached before sending
        if settings.enable_email:
            bundle["email_recipients"].update(_get_admin_emails(settings))
        if settings.enable_sms:
            bundle["sms_recipients"].update(_get_admin_mobiles(settings))

        if settings.enable_email and bundle["email_recipients"]:
            if _send_email_alert(bundle):
                email_count += 1

        if settings.enable_sms and bundle["sms_recipients"]:
            if _send_sms_alert(bundle, settings):
                sms_count += 1

    frappe.logger().info(
        "Document alerts: %s email(s) and %s SMS alert(s) sent for %s record(s).",
        email_count,
        sms_count,
        len(bundles),
    )


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
            child.expiry_date,
            child.alert_days,
            child.notes,
            dt.alert_days as default_alert_days
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
            child.name as rowname,
            child.document_type,
            child.expiry_date,
            child.alert_days,
            child.notes,
            dt.alert_days as default_alert_days
        from `tabCustomer Employee Registration` parent
        inner join `tabDocument Detail` child
            on child.parent = parent.name
            and child.parenttype = 'Customer Employee Registration'
            and child.parentfield = 'document_details'
        left join `tabDocument Type Master` dt
            on dt.name = child.document_type
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
            bundle["allow_email"] = bool(row.get(email_flag))
            bundle["allow_sms"] = bool(row.get(sms_flag))

        bundle["documents"].append(entry)

        if bundle["allow_email"]:
            bundle["email_recipients"].update(_collect_row_contacts(row, email_fields))

        if bundle["allow_sms"]:
            bundle["sms_recipients"].update(_collect_row_contacts(row, sms_fields))

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

    return {
        "document_type": row.get("document_type") or "Document",
        "expiry_date": expiry,
        "days_left": days_left,
        "notes": row.get("notes") or "",
    }


def _send_email_alert(bundle):
    recipients = sorted(bundle["email_recipients"])
    if not recipients:
        return False

    subject = f"Document Expiry Alert - {bundle['title']}"
    message = _render_email_body(bundle)

    frappe.sendmail(recipients=recipients, subject=subject, message=message)
    return True


def _render_email_body(bundle):
    link = get_link_to_form(bundle["parenttype"], bundle["parent"])
    rows_html = []

    for doc in bundle["documents"]:
        note = escape_html(doc["notes"]) if doc["notes"] else ""
        rows_html.append(
            f"""
            <tr>
                <td>{escape_html(doc["document_type"])}</td>
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

    return f"""
        <p>The following document(s) for <strong>{escape_html(bundle['title'])}</strong> are due soon:</p>
        {table}
        <p>Record: {link}</p>
    """


def _send_sms_alert(bundle, settings):
    recipients = sorted(bundle["sms_recipients"])
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

    frappe.send_sms(recipients=recipients, msg=sms)
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
