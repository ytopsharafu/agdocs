from __future__ import annotations

import frappe


def execute():
    report_name = "Bank Balance"

    if not frappe.db.exists("Report", report_name):
        return

    frappe.db.delete("Report Filter", {"parent": report_name})
    frappe.delete_doc("Report", report_name, force=1, ignore_permissions=True)
