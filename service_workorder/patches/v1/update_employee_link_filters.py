import json
from pathlib import Path

import frappe


SCRIPT_NAMES = [
    "emp_filter",
    "emp_filter_sales_order",
    "emp_filter_sales_invoice",
]


def execute():
    fixture_path = Path(
        frappe.get_app_path(
            "service_workorder",
            "fixtures",
            "client_script",
            "client_script.json",
        )
    )

    fixtures = json.loads(fixture_path.read_text())
    fixtures_by_name = {doc["name"]: doc for doc in fixtures}

    for script_name in SCRIPT_NAMES:
        doc = fixtures_by_name.get(script_name)
        if not doc:
            frappe.throw(f"Client Script fixture '{script_name}' not found")

        upsert_client_script(doc)

    frappe.clear_cache(doctype="Service Request")
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Sales Invoice")


def upsert_client_script(doc):
    payload = {
        "doctype": "Client Script",
        "dt": doc.get("dt"),
        "name": doc.get("name"),
        "module": doc.get("module"),
        "view": doc.get("view") or "Form",
        "enabled": doc.get("enabled", 1),
        "script": doc.get("script"),
    }

    if frappe.db.exists("Client Script", payload["name"]):
        script_doc = frappe.get_doc("Client Script", payload["name"])
        script_doc.update(payload)
        script_doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(payload).insert(ignore_permissions=True)
