import frappe

@frappe.whitelist()
def make_sales_order_from_service_request(service_request):
    """Prepare a new Sales Order draft based on Service Request items."""
    doc = frappe.get_doc("Service Request", service_request)
    so = frappe.new_doc("Sales Order")

    so.customer = doc.customer
    so.company = doc.company or frappe.defaults.get_user_default("Company")

    for item in doc.work_details:
        if item.status == "Completed":
            so.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_code,
                "qty": item.qty,
                "rate": (item.gov_charge or 0) + (item.service_charge or 0),
                "description": f"Gov: {item.gov_charge} | Service: {item.service_charge}"
            })

    return so.as_dict()
