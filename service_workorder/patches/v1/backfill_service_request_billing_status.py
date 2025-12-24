import frappe


def execute():
    names = frappe.get_all("Service Request", pluck="name")
    for name in names:
        try:
            doc = frappe.get_doc("Service Request", name)
            if hasattr(doc, "_derive_billing_status"):
                status = doc._derive_billing_status()
                frappe.db.set_value(
                    "Service Request",
                    name,
                    "billing_status",
                    status,
                    update_modified=False,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Failed to backfill SR billing status")
