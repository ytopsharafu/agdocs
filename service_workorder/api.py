import frappe
from frappe.utils import nowdate, add_days


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
# LOAD SERVICE CHARGE FROM SLAB
# ============================================================
@frappe.whitelist()
def get_service_charge_from_slab(slab_name, item_code):
    if not slab_name or not item_code:
        return {}
    return frappe.db.get_value(
        "Service Charge Slab Item",
        {"parent": slab_name, "item": item_code},
        "service_charge",
        as_dict=True
    ) or {}


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

    # Prevent double creation
    _check_existing_links(sr)

    # Create SO
    so = frappe.new_doc("Sales Order")
    so.customer = sr.customer
    so.company = sr.company
    so.transaction_date = nowdate()
    so.delivery_date = add_days(nowdate(), 1)

    # Mandatory fields
    so.tax_category = sr.tax_category
    so.selling_price_list = sr.price_list
    so.price_list_currency = frappe.db.get_value("Price List", sr.price_list, "currency")
    so.custom_service_charge_slab = sr.service_charge_slab
    so.taxes_and_charges = sr.sales_taxes_and_charges_template

    # Employee info
    so.custom_employee = sr.dep_emp_name or ""
    so.custom_employee_type = sr.employee_type or ""
    so.custom_dep_no = sr.department_no or ""
    so.custom_uid_no = sr.uid_no or ""

    # NAMING SERIES
    customer_group = frappe.db.get_value("Customer", sr.customer, "customer_group")
    if customer_group == "VAT":
        so.naming_series = "SAL-ORD-.YYYY.-"
    elif customer_group == "NON VAT":
        so.naming_series = "SAL-ORD-NV-.YYYY.-"
    else:
        so.naming_series = "SAL-ORD-.YYYY.-"

    # Add items
    for row in sr.work_details:
        item_name, stock_uom = frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom"])
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

    # Add taxes WITH row_id FIX
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

            # REQUIRED row_id assignment
            if t.charge_type in ["On Previous Row Amount", "On Previous Row Total"]:
                tax_row["row_id"] = idx - 1

            so.append("taxes", tax_row)

    # Insert
    so.flags.ignore_permissions = True
    so.flags.ignore_mandatory = True
    so.insert(ignore_permissions=True)
    so.save(ignore_permissions=True)

    # Link back
    frappe.db.set_value("Service Request", sr.name, "sales_order_ref", so.name)

    return {"name": so.name}


# ============================================================
# 2️⃣ CREATE SALES INVOICE FROM SERVICE REQUEST
# ============================================================
@frappe.whitelist()
def create_sales_invoice_from_service_request(service_request):
    sr = frappe.get_doc("Service Request", service_request)

    # Prevent double creation
    _check_existing_links(sr)

    # Create SI
    si = frappe.new_doc("Sales Invoice")
    si.customer = sr.customer
    si.company = sr.company
    si.posting_date = nowdate()

    # Mandatory fields
    si.tax_category = sr.tax_category
    si.selling_price_list = sr.price_list
    si.price_list_currency = frappe.db.get_value("Price List", sr.price_list, "currency")
    si.custom_service_charge_slab = sr.service_charge_slab
    si.taxes_and_charges = sr.sales_taxes_and_charges_template

    # Employee info
    si.custom_employee = sr.dep_emp_name or ""
    si.custom_employee_type = sr.employee_type or ""
    si.custom_dep_no = sr.department_no or ""
    si.custom_uid_no = sr.uid_no or ""

    # NAMING SERIES
    customer_group = frappe.db.get_value("Customer", sr.customer, "customer_group")
    if customer_group == "VAT":
        si.naming_series = "ACC-SINV-.YYYY.-"
    elif customer_group == "NON VAT":
        si.naming_series = "INV-.YYYY.-"
    else:
        si.naming_series = "INV-.YYYY.-"

    # Add items
    for row in sr.work_details:
        item_name, stock_uom = frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom"])
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

    # Add taxes WITH row_id FIX
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

            # REQUIRED row_id assignment
            if t.charge_type in ["On Previous Row Amount", "On Previous Row Total"]:
                tax_row["row_id"] = idx - 1

            si.append("taxes", tax_row)

    # Insert
    si.flags.ignore_permissions = True
    si.flags.ignore_mandatory = True
    si.insert(ignore_permissions=True)
    si.save(ignore_permissions=True)

    # Link back
    frappe.db.set_value("Service Request", sr.name, "sales_invoice_ref", si.name)

    return {"name": si.name}


# ============================================================
# HANDLE DELETE / CANCEL / AMEND: CLEAR OR UPDATE LINKS
# ============================================================
@frappe.whitelist()
def clear_sr_links(doc, event=None):
    """Clear links when Sales Order or Sales Invoice is deleted or cancelled."""
    if doc.doctype == "Sales Order":
        sr = frappe.db.get_value("Service Request", {"sales_order_ref": doc.name}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_order_ref", "")

    if doc.doctype == "Sales Invoice":
        sr = frappe.db.get_value("Service Request", {"sales_invoice_ref": doc.name}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_invoice_ref", "")


@frappe.whitelist()
def update_amended_link(doc, event=None):
    """Update Service Request link when SO/SI is amended."""
    if not doc.amended_from:
        return

    old = doc.amended_from
    new = doc.name

    if doc.doctype == "Sales Order":
        sr = frappe.db.get_value("Service Request", {"sales_order_ref": old}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_order_ref", new)

    if doc.doctype == "Sales Invoice":
        sr = frappe.db.get_value("Service Request", {"sales_invoice_ref": old}, "name")
        if sr:
            frappe.db.set_value("Service Request", sr, "sales_invoice_ref", new)

import frappe

# ============================================================
# VALIDATE SR CANCEL/DELETE
# ============================================================
@frappe.whitelist()
def validate_sr_cancel_or_delete(sr_name):
    """Ensure SR cannot be cancelled/deleted if linked SO/SI is still active."""
    sr = frappe.get_doc("Service Request", sr_name)

    if sr.sales_order_ref:
        so_status = frappe.db.get_value("Sales Order", sr.sales_order_ref, "docstatus")
        if so_status and so_status != 2:  # 2 = Cancelled
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Order <b>{sr.sales_order_ref}</b> is active. Cancel it first."
            )

    if sr.sales_invoice_ref:
        si_status = frappe.db.get_value("Sales Invoice", sr.sales_invoice_ref, "docstatus")
        if si_status and si_status != 2:
            frappe.throw(
                f"❗ Cannot cancel/delete Service Request while Sales Invoice <b>{sr.sales_invoice_ref}</b> is active. Cancel it first."
            )

    return True
