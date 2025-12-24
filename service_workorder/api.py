import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_default_contact
from frappe.utils import nowdate, add_days, cint


# ============================================================
# COMMON: Prevent double creation (ONLY one allowed - SO or SI)
# ============================================================
def _check_existing_links(sr):
    if getattr(sr, "sales_order_ref", None):
        frappe.throw(f"❗ Sales Order already exists: <b>{sr.sales_order_ref}</b>")
    if getattr(sr, "sales_invoice_ref", None):
        frappe.throw(f"❗ Sales Invoice already exists: <b>{sr.sales_invoice_ref}</b>")


# ============================================================
# LOAD TAX TEMPLATE (Used in client script)
# ============================================================
@frappe.whitelist()
def load_sales_taxes(template_name=None, company=None):
    if not template_name:
        return []

    doc = frappe.get_doc("Sales Taxes and Charges Template", template_name)
    return [
        {
            "charge_type": tax.charge_type,
            "account_head": tax.account_head,
            "description": tax.description,
            "rate": tax.rate,
            "cost_center": tax.cost_center,
        }
        for tax in doc.taxes
    ]


# ============================================================
# Customer contact info helper for client scripts
# ============================================================
@frappe.whitelist()
def get_customer_contact_info(customer):
    if not customer:
        return {}

    fields = ["customer_name", "email_id"]
    for column in ("mobile_no", "phone"):
        if frappe.db.has_column("Customer", column):
            fields.append(column)

    info = frappe.db.get_value("Customer", customer, fields, as_dict=True)
    if not info:
        return {}

    result = {
        "customer": customer,
        "customer_name": info.get("customer_name"),
        "customer_email": info.get("email_id"),
    }

    for column in ("mobile_no", "phone"):
        if info.get(column):
            result["mobile"] = info.get(column)
            break

    contact_name = get_default_contact("Customer", customer)
    if contact_name:
        contact = frappe.db.get_value(
            "Contact",
            contact_name,
            ["name", "email_id", "mobile_no", "phone"],
            as_dict=True,
        )
        if contact:
            result["primary_contact"] = contact_name
            result["contact_email"] = contact.get("email_id")
            contact_mobile = contact.get("mobile_no") or contact.get("phone")
            if contact_mobile:
                result["contact_mobile"] = contact_mobile
                if not result.get("mobile"):
                    result["mobile"] = contact_mobile

            if not result.get("customer_email") and contact.get("email_id"):
                result["customer_email"] = contact.get("email_id")

    return result


@frappe.whitelist()
def find_existing_document_registration(customer, exclude=None):
    if not customer:
        return {}

    filters = {
        "customer": customer,
        "docstatus": ("<", 2),
    }

    if exclude:
        filters["name"] = ("!=", exclude)

    rows = frappe.get_all(
        "Customer Document Registration",
        filters=filters,
        fields=["name", "customer", "customer_name", "active"],
        limit=1,
    )

    return rows[0] if rows else {}


@frappe.whitelist()
def find_document_number_usage(document_number, parent=None, parenttype=None, rowname=None):
    value = (document_number or "").strip()
    if not value:
        return {}

    normalized = value.lower()

    rows = frappe.db.sql(
        """
        select
            name,
            parent,
            parenttype,
            document_number
        from `tabDocument Detail`
        where lower(document_number) = %s
        """,
        normalized,
        as_dict=True,
    )

    for row in rows:
        if (
            parent
            and parenttype
            and row.parenttype == parenttype
            and row.parent == parent
        ):
            if rowname and row.name == rowname:
                continue
        return row

    return {}


@frappe.whitelist()
@frappe.read_only()
def get_uid_length_limits():
    settings = frappe.get_cached_doc("Document Alert Settings")
    min_length = cint(settings.get("uid_min_length")) or 7
    max_length = cint(settings.get("uid_max_length")) or 15

    if min_length < 1:
        min_length = 1
    if max_length < min_length:
        max_length = min_length

    return {"min": min_length, "max": max_length}


def ensure_sales_order_delivery_date(doc, _method=None):
    """Fill delivery date automatically so users aren't blocked by mandatory field."""
    if getattr(doc, "delivery_date", None):
        return

    doc.delivery_date = doc.transaction_date or nowdate()
    for row in getattr(doc, "items", []) or []:
        ensure_sales_order_item_delivery_date(row, doc)


def ensure_sales_order_item_delivery_date(row, parent_doc=None):
    """Fill delivery date on the child row if missing."""
    reference_date = None
    if parent_doc:
        reference_date = getattr(parent_doc, "delivery_date", None) or getattr(parent_doc, "transaction_date", None)

    if reference_date is None:
        reference_date = nowdate()

    if getattr(row, "delivery_date", None):
        return

    row.delivery_date = reference_date


# ============================================================
# Get service charge for an item from a slab
# ============================================================
@frappe.whitelist()
def get_service_charge_from_slab(slab=None, item=None, slab_name=None, item_code=None):
    # Support both naming styles
    slab = slab or slab_name
    item = item or item_code

    if not slab or not item:
        return {}

    row = frappe.db.get_value(
        "Service Charge Slab Item",
        {"parent": slab, "item": item},
        ["service_charge", "tax_applicable"],
        as_dict=True
    )

    return row or {}


# ============================================================
# PRODUCT BUNDLE HELPER FOR SERVICE REQUEST JOBS
# ============================================================
@frappe.whitelist()
def get_product_bundle_items(product_bundle):
    if not product_bundle:
        return []

    bundle = frappe.get_doc("Product Bundle", product_bundle)
    items = []
    for row in bundle.items:
        if not row.item_code:
            continue
        item_info = frappe.db.get_value(
            "Item",
            row.item_code,
            ["item_name", "is_sales_item"],
            as_dict=True,
        )
        if not (item_info and cint(item_info.is_sales_item) != 0):
            continue
        items.append(
            {
                "item_code": row.item_code,
                "item_name": item_info.item_name or row.item_code,
                "qty": row.qty or 1,
                "description": row.description or "",
            }
        )
    return items


@frappe.whitelist()
def check_employee_completion_warning(employee=None, service_request=None, completed_in_doc=0):
    if not employee:
        return {}

    details = frappe.db.get_value(
        "Customer Employee Registration",
        employee,
        ["new_employee"],
        as_dict=True,
    )
    if not details or cint(details.get("new_employee")) == 0:
        return {}

    settings = frappe.get_cached_doc("Document Alert Settings")
    if not cint(settings.get("enable_completion_warning")):
        return {}

    threshold = cint(settings.get("completion_warning_threshold")) or 4
    if threshold <= 0:
        threshold = 4

    window_days = cint(settings.get("completion_warning_window")) or 0

    completed_in_doc = cint(completed_in_doc or 0)

    exclude_clause = ""
    filters = [employee]
    if service_request:
        exclude_clause = "and sr.name != %s"
        filters.append(service_request)

    date_clause = ""
    if window_days > 0:
        cutoff_date = add_days(nowdate(), -window_days)
        date_clause = "and coalesce(item.item_date, sr.modified) >= %s"
        filters.append(cutoff_date)

    count = frappe.db.sql(
        f"""
        select count(*)
        from `tabService Request Item` item
        inner join `tabService Request` sr on sr.name = item.parent
        where item.status = 'Completed'
          and sr.dep_emp_name = %s
          and coalesce(sr.docstatus, 0) < 2
          {exclude_clause}
          {date_clause}
        """,
        filters,
    )[0][0]

    total = count + completed_in_doc
    if total >= threshold:
        timeframe = ""
        if window_days > 0:
            timeframe = _(" in the last {0} days").format(window_days)
        return {
            "warning": _(
                "Employee {0} already has {1} completed work items{2} across Service Requests. Please update the UID number as soon as possible."
            ).format(employee, total, timeframe)
        }

    return {}


# ============================================================
# GET SALES TAX TEMPLATE USING CORRECT FIELD
# ============================================================
@frappe.whitelist()
def get_sales_tax_template(company, tax_category):
    if not company or not tax_category:
        return ""

    return frappe.db.get_value(
        "Tax Rule",
        {
            "company": company,
            "tax_type": "Sales",
            "tax_category": tax_category,
        },
        "sales_tax_template"
    ) or ""


# ============================================================
# 1️⃣ CREATE SALES ORDER FROM SERVICE REQUEST
# ============================================================
@frappe.whitelist()
def create_sales_order_from_service_request(service_request):
    sr = frappe.get_doc("Service Request", service_request)

    _check_existing_links(sr)

    so = frappe.new_doc("Sales Order")
    so.customer = sr.customer
    so.company = sr.company
    so.transaction_date = nowdate()
    so.delivery_date = add_days(nowdate(), 1)

    so.tax_category = sr.tax_category
    so.selling_price_list = sr.price_list
    so.price_list_currency = frappe.db.get_value("Price List", sr.price_list, "currency")
    so.custom_service_charge_slab = sr.service_charge_slab
    so.taxes_and_charges = sr.sales_taxes_and_charges_template

    so.custom_employee = sr.dep_emp_name or ""
    so.custom_employee_type = sr.employee_type or ""
    so.custom_dep_no = sr.department_no or ""
    so.custom_uid_no = sr.uid_no or ""
    so.custom_service_request = sr.name

    customer_group = frappe.db.get_value("Customer", sr.customer, "customer_group")
    if customer_group == "VAT":
        so.naming_series = "SAL-ORD-.YYYY.-"
    elif customer_group == "NON VAT":
        so.naming_series = "SAL-ORD-NV-.YYYY.-"
    else:
        so.naming_series = "SAL-ORD-.YYYY.-"

    for row in sr.work_details:
        item_name, stock_uom = frappe.db.get_value(
            "Item", row.item_code, ["item_name", "stock_uom"]
        )
        so.append("items", {
            "item_code": row.item_code,
            "item_name": item_name,
            "qty": row.qty,
            "uom": stock_uom,
            "rate": row.gov_charge,
            "custom_service_charge": row.service_charge,
            "custom_total_with_service_charge": row.amount,
            "description": row.item_code,
            "delivery_date": add_days(nowdate(), 1),
        })

    so.set("taxes", [])
    if sr.sales_taxes_and_charges_template:
        template = frappe.get_doc("Sales Taxes and Charges Template", sr.sales_taxes_and_charges_template)

        for idx, t in enumerate(template.taxes, start=1):
            tax_row = {
                "charge_type": t.charge_type,
                "account_head": t.account_head,
                "rate": t.rate,
                "description": t.description,
                "cost_center": t.cost_center
            }

            if t.charge_type in ["On Previous Row Amount", "On Previous Row Total"]:
                tax_row["row_id"] = idx - 1

            so.append("taxes", tax_row)

    so.flags.ignore_permissions = True
    so.flags.ignore_mandatory = True
    so.insert(ignore_permissions=True)
    so.save(ignore_permissions=True)

    frappe.db.set_value("Service Request", sr.name, {
        "sales_order_ref": so.name,
        "billing_status": "Sales Order Created",
    })
    _refresh_service_request_billing(sr.name)

    # Return the synced document so client scripts can route without extra fetches
    return so.as_dict()


# ============================================================
# 2️⃣ CREATE SALES INVOICE FROM SERVICE REQUEST
# ============================================================
@frappe.whitelist()
def create_sales_invoice_from_service_request(service_request):
    sr = frappe.get_doc("Service Request", service_request)

    _check_existing_links(sr)

    incomplete = [
        row.idx or row.item_code
        for row in sr.work_details
        if (row.status or "").strip().lower() != "completed"
    ]
    if incomplete:
        frappe.throw(
            _("Cannot create Sales Invoice while the following rows are not Completed: {0}").format(
                ", ".join(str(v) for v in incomplete)
            )
        )

    si = frappe.new_doc("Sales Invoice")
    si.customer = sr.customer
    si.company = sr.company
    si.posting_date = nowdate()

    si.tax_category = sr.tax_category
    si.selling_price_list = sr.price_list
    si.price_list_currency = frappe.db.get_value("Price List", sr.price_list, "currency")
    si.custom_service_charge_slab = sr.service_charge_slab
    si.taxes_and_charges = sr.sales_taxes_and_charges_template

    si.custom_employee = sr.dep_emp_name or ""
    si.custom_employee_type = sr.employee_type or ""
    si.custom_dep_no = sr.department_no or ""
    si.custom_uid_no = sr.uid_no or ""
    si.custom_service_request = sr.name

    customer_group = frappe.db.get_value("Customer", sr.customer, "customer_group")
    if customer_group == "VAT":
        si.naming_series = "ACC-SINV-.YYYY.-"
    elif customer_group == "NON VAT":
        si.naming_series = "INV-.YYYY.-"
    else:
        si.naming_series = "INV-.YYYY.-"

    for row in sr.work_details:
        item_name, stock_uom = frappe.db.get_value(
            "Item", row.item_code, ["item_name", "stock_uom"]
        )
        si.append("items", {
            "item_code": row.item_code,
            "item_name": item_name,
            "qty": row.qty,
            "uom": stock_uom,
            "rate": row.gov_charge,
            "custom_service_charge": row.service_charge,
            "custom_total_with_service_charge": row.amount,
            "description": row.item_code,
        })

    si.set("taxes", [])
    if sr.sales_taxes_and_charges_template:
        template = frappe.get_doc("Sales Taxes and Charges Template", sr.sales_taxes_and_charges_template)

        for idx, t in enumerate(template.taxes, start=1):
            tax_row = {
                "charge_type": t.charge_type,
                "account_head": t.account_head,
                "rate": t.rate,
                "description": t.description,
                "cost_center": t.cost_center,
            }

            if t.charge_type in ["On Previous Row Amount", "On Previous Row Total"]:
                tax_row["row_id"] = idx - 1

            si.append("taxes", tax_row)

    si.flags.ignore_permissions = True
    si.flags.ignore_mandatory = True
    si.insert(ignore_permissions=True)
    si.save(ignore_permissions=True)

    frappe.db.set_value("Service Request", sr.name, {
        "sales_invoice_ref": si.name,
        "billing_status": "Invoiced",
    })
    _refresh_service_request_billing(sr.name)

    return si.as_dict()


# ============================================================
# HANDLE DELETE / CANCEL / AMEND: CLEAR OR UPDATE LINKS
# ============================================================
@frappe.whitelist()
def clear_sr_links(doc, event=None):
    if doc.doctype == "Sales Order":
        sr = frappe.db.get_value("Service Request", {"sales_order_ref": doc.name}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_order_ref", "")
            _refresh_service_request_billing(sr)

    if doc.doctype == "Sales Invoice":
        sr = frappe.db.get_value("Service Request", {"sales_invoice_ref": doc.name}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_invoice_ref", "")
            _refresh_service_request_billing(sr)


@frappe.whitelist()
def update_amended_link(doc, event=None):
    if not doc.amended_from:
        return

    old = doc.amended_from
    new = doc.name

    if doc.doctype == "Sales Order":
        sr = frappe.db.get_value("Service Request", {"sales_order_ref": old}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_order_ref", new)
            _refresh_service_request_billing(sr)

    if doc.doctype == "Sales Invoice":
        sr = frappe.db.get_value("Service Request", {"sales_invoice_ref": old}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_invoice_ref", new)
            _refresh_service_request_billing(sr)

@frappe.whitelist()
def validate_sr_cancel_or_delete(sr_name):
    doc = frappe.get_doc("Service Request", sr_name)

    # Sales Order check
    if doc.sales_order_ref:
        so_status = frappe.db.get_value("Sales Order", doc.sales_order_ref, "docstatus")
        if so_status and so_status != 2:
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Order <b>{doc.sales_order_ref}</b> is active."
            )

    # Sales Invoice check
    if doc.sales_invoice_ref:
        si_status = frappe.db.get_value("Sales Invoice", doc.sales_invoice_ref, "docstatus")
        if si_status and si_status != 2:
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Invoice <b>{doc.sales_invoice_ref}</b> is active."
            )


def _refresh_service_request_billing(sr_name):
    try:
        doc = frappe.get_doc("Service Request", sr_name)
    except frappe.DoesNotExistError:
        return

    if hasattr(doc, "_derive_billing_status"):
        status = doc._derive_billing_status()
        frappe.db.set_value(
            "Service Request",
            sr_name,
            "billing_status",
            status,
            update_modified=False,
        )

    return True

def hook_validate_sr_cancel_or_delete(doc, method=None):
    # Same logic

    if doc.sales_order_ref:
        so_status = frappe.db.get_value("Sales Order", doc.sales_order_ref, "docstatus")
        if so_status and so_status != 2:
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Order <b>{doc.sales_order_ref}</b> is active."
            )

    if doc.sales_invoice_ref:
        si_status = frappe.db.get_value("Sales Invoice", doc.sales_invoice_ref, "docstatus")
        if si_status and si_status != 2:
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Invoice <b>{doc.sales_invoice_ref}</b> is active."
            )
#date_fetch#

import frappe

# ============================================================
# 1. ONE-TIME BACKFILL FOR EXISTING ROWS
# ============================================================
@frappe.whitelist()
def backfill_item_dates():
    """Fill item_date for old rows based on true creation timestamp."""
    items = frappe.get_all(
        "Service Request Item",
        fields=["name", "creation"],
        filters={"item_date": ["in", ["", None]]}
    )

    updated = 0

    for item in items:
        creation_date = item.creation.date()

        frappe.db.set_value(
            "Service Request Item",
            item.name,
            "item_date",
            creation_date,
            update_modified=False
        )
        updated += 1

    return f"Updated {updated} item rows successfully."


# ============================================================
# 2. AUTO-SET ITEM DATE FOR NEW ROWS (AFTER SAVE)
# ============================================================
@frappe.whitelist()
def set_item_creation_dates(docname):
    """After each save, sync item_date with true row creation datetime."""
    items = frappe.get_all(
        "Service Request Item",
        filters={"parent": docname},
        fields=["name", "creation"]
    )

    for item in items:
        creation_date = item.creation.date()

        frappe.db.set_value(
            "Service Request Item",
            item.name,
            "item_date",
            creation_date,
            update_modified=False
        )

    return "ok"
