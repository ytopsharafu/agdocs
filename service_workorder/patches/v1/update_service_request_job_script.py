import json

import frappe


TARGET_SCRIPTS = [
    "tax_and_cat",  # Service Request job/price logic
    "main_emp_filter",  # Customer Employee Registration guards
]


def fetch_fixture_scripts():
    fixture_path = frappe.get_app_path(
        "service_workorder",
        "fixtures",
        "client_script",
        "client_script.json",
    )
    with open(fixture_path) as handle:
        data = json.load(handle)

    mapping = {}
    for record in data:
        name = record.get("name")
        if name in TARGET_SCRIPTS:
            mapping[name] = (record.get("script") or "").strip()
    return mapping


def sync_script(name, script):
    if not script:
        return

    try:
        doc = frappe.get_doc("Client Script", name)
    except frappe.DoesNotExistError:
        return

    doc.script = script
    doc.enabled = 1
    doc.save(ignore_permissions=True)


def execute():
    scripts = fetch_fixture_scripts()
    for name, script in scripts.items():
        sync_script(name, script)
