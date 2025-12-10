"""
Remove orphaned custom blocks from all workspaces.

Existing workspaces in the demo site reference custom HTML blocks that have
already been deleted. Whenever a user edits such a workspace, Frappe raises a
LinkValidationError (e.g. "Could not find Row #1: Custom Block Name: Bank/Card").
This patch scans every Workspace record, drops the broken link rows, and removes
their matching entries from the JSON `content` field so editors can remove or
rearrange blocks without errors.
"""

from __future__ import annotations

import json

import frappe


def execute() -> None:
    if not frappe.db.table_exists("Workspace"):
        return

    existing_blocks = set(frappe.get_all("Custom HTML Block", pluck="name"))

    workspaces = frappe.get_all("Workspace", pluck="name")
    if not workspaces:
        return

    for ws_name in workspaces:
        doc = frappe.get_doc("Workspace", ws_name)
        removed = False

        for row in list(doc.custom_blocks or []):
            block_name = (row.custom_block_name or "").strip()
            if block_name and block_name not in existing_blocks:
                doc.remove(row)
                removed = True

        new_layout = []
        if doc.content:
            try:
                layout = json.loads(doc.content)
            except Exception:
                layout = []

            for block in layout:
                if (
                    block.get("type") == "custom_block"
                    and (block.get("data") or {}).get("custom_block_name") not in existing_blocks
                ):
                    removed = True
                    continue
                new_layout.append(block)

            if removed:
                doc.content = json.dumps(new_layout, separators=(",", ":"))

        if removed:
            doc.flags.ignore_permissions = True
            doc.save()

