import frappe
from frappe.utils import nowdate

# service charge laoder
@frappe.whitelist()
def get_service_charge_from_slab(slab_name, item_code):
    """Fetch the service charge for the given item from the given slab"""
    if not slab_name or not item_code:
        return {}

    result = frappe.db.get_value(
        "Service Charge Slab Item",
        {"parent": slab_name, "item": item_code},
        ["service_charge"],
        as_dict=True
    )
    return result or {}

# ============================================================
# 1️⃣ Fetch Service Charge for Item (used by Client Script)
# ============================================================
@frappe.whitelist()
def get_item_service_charge(slab, item):
    """Return service charge for an item from the given slab."""
    rows = frappe.get_all(
        "Service Charge Slab Item",
        filters={"parent": slab, "item": item},
        fields=["service_charge", "tax_applicable"],
        limit=1,
        ignore_permissions=True,  # ✅ bypasses permission check
    )
    return rows[0] if rows else {}


# ============================================================
# 2️⃣ Create Sales Order from Service Request
# ============================================================
@frappe.whitelist()
def create_sales_order_from_service_request(service_request):
    """Open new Sales Order prefilled with main & SRV items from both tabs (grouped by item)."""
    if not service_request:
        frappe.throw("Service Request ID is required")

    sr = frappe.get_doc("Service Request", service_request)

    # --- Detect customer field ---
    customer = getattr(sr, "customer", None) or getattr(sr, "customer_name", None) or getattr(sr, "client", None)
    if not customer:
        frappe.throw("Customer not found in Service Request")

    # --- Create Sales Order ---
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = getattr(sr, "company", None)
    so.service_request = sr.name  # (Add a Link field in Sales Order)
    so.set("items", [])

    # --- Map SRV items by main item_code ---
    srv_map = {}
    if hasattr(sr, "table_sgku"):
        for srv in sr.table_sgku:
            if srv.item_code:
                clean_code = srv.item_code.replace("SRV ", "").strip()
                srv_map[clean_code] = srv

    # --- Add main items and related SRV items ---
    if hasattr(sr, "work_details"):
        for main in sr.work_details:
            total_rate = (main.gov_charge or 0) + (main.service_charge or 0)
            so.append("items", {
                "item_code": main.item_code,
                "qty": main.qty,
                "rate": total_rate,
                "description": f"Main Item | Gov: {main.gov_charge or 0}, SRV: {main.service_charge or 0}",
            })

            # related SRV item (if any)
            srv_row = srv_map.get(main.item_code)
            if srv_row:
                so.append("items", {
                    "item_code": srv_row.item_code,
                    "qty": srv_row.qty or main.qty,
                    "rate": srv_row.service_charge or 0,
                    "description": f"→ SRV for {main.item_code} | Service Charge: {srv_row.service_charge or 0}",
                })

    # --- Add unlinked SRV items ---
    if hasattr(sr, "table_sgku"):
        for srv in sr.table_sgku:
            linked = any(
                srv.item_code.replace("SRV ", "").strip() == m.item_code
                for m in sr.work_details or []
            )
            if not linked:
                so.append("items", {
                    "item_code": srv.item_code,
                    "qty": srv.qty or 1,
                    "rate": srv.service_charge or 0,
                    "description": f"Unlinked SRV Item | Service Charge: {srv.service_charge or 0}",
                })

    return so.as_dict()


# ============================================================
# 3️⃣ Create Sales Invoice from Service Request
# ============================================================
@frappe.whitelist()
def create_sales_invoice_from_service_request(service_request):
    """Create Sales Invoice only if SR is submitted and all items are completed."""
    if not service_request:
        frappe.throw("Service Request ID is required")

    sr = frappe.get_doc("Service Request", service_request)

    # --- Validations ---
    if sr.docstatus != 1:
        frappe.throw("You can only create Sales Invoice after submitting the Service Request.")

    if sr.sales_order_ref:
        frappe.throw("This Service Request already has a Sales Order. You can only create either a Sales Order or a Sales Invoice.")

    incomplete = [row.item_code for row in sr.work_details if row.status != "Completed"]
    if incomplete:
        frappe.throw(f"All items must be Completed before creating Sales Invoice. Incomplete: {', '.join(incomplete)}")

    # --- Detect customer field ---
    customer = getattr(sr, "customer", None) or getattr(sr, "customer_name", None) or getattr(sr, "client", None)
    if not customer:
        frappe.throw("Customer not found in Service Request")

    # --- Create Sales Invoice ---
    si = frappe.new_doc("Sales Invoice")
    si.customer = customer
    si.company = getattr(sr, "company", None)
    si.service_request = sr.name
    si.posting_date = nowdate()
    si.set("items", [])

    # --- Add completed main items ---
    if hasattr(sr, "work_details"):
        for row in sr.work_details:
            if row.status != "Completed":
                continue

            item_doc = frappe.get_doc("Item", row.item_code)
            total_rate = (row.gov_charge or 0) + (row.service_charge or 0)
            si.append("items", {
                "item_code": row.item_code,
                "item_name": item_doc.item_name,
                "uom": item_doc.stock_uom,
                "qty": row.qty,
                "rate": total_rate,
                "description": f"Main Item | Gov: {row.gov_charge or 0}, SRV: {row.service_charge or 0}",
            })

    # --- Add SRV items from 2nd tab ---
    if hasattr(sr, "table_sgku"):
        for row in sr.table_sgku:
            item_doc = frappe.get_doc("Item", row.item_code)
            si.append("items", {
                "item_code": row.item_code,
                "item_name": item_doc.item_name,
                "uom": item_doc.stock_uom,
                "qty": row.qty or 1,
                "rate": row.service_charge or 0,
                "description": f"SRV Item | Service Charge: {row.service_charge or 0}",
            })

    return si.as_dict()

