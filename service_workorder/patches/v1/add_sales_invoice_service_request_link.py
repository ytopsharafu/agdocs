import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
    if frappe.db.exists("Custom Field", "Sales Invoice-custom_service_request"):
        return

    create_custom_field(
        "Sales Invoice",
        {
            "fieldname": "custom_service_request",
            "label": "Service Request",
            "fieldtype": "Link",
            "options": "Service Request",
            "insert_after": "po_no",
        },
    )
