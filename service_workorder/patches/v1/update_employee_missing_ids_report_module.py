import frappe


def execute():
    if not frappe.db.exists("Report", "Employee Missing IDs"):
        return

    frappe.db.set_value(
        "Report",
        "Employee Missing IDs",
        "module",
        "Service Workorder",
        update_modified=False,
    )
