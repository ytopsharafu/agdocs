from __future__ import annotations

import frappe


def execute() -> None:
    if frappe.db.exists("Client Script", "main_emp_filter"):
        frappe.delete_doc("Client Script", "main_emp_filter", ignore_permissions=True)
