import frappe


def execute():
    _backfill_sales_orders()
    _backfill_sales_invoices()


def _backfill_sales_orders():
    service_requests = frappe.get_all(
        "Service Request",
        fields=["name", "sales_order_ref"],
        filters={"sales_order_ref": ["not in", ("", None)]},
    )

    for sr in service_requests:
        if not frappe.db.exists("Sales Order", sr.sales_order_ref):
            continue

        frappe.db.set_value(
            "Sales Order",
            sr.sales_order_ref,
            "custom_service_request",
            sr.name,
            update_modified=False,
        )


def _backfill_sales_invoices():
    service_requests = frappe.get_all(
        "Service Request",
        fields=["name", "sales_invoice_ref"],
        filters={"sales_invoice_ref": ["not in", ("", None)]},
    )

    for sr in service_requests:
        if not frappe.db.exists("Sales Invoice", sr.sales_invoice_ref):
            continue

        frappe.db.set_value(
            "Sales Invoice",
            sr.sales_invoice_ref,
            "custom_service_request",
            sr.name,
            update_modified=False,
        )
