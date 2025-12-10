"""Workspace-related hooks."""

from __future__ import annotations

import json

import frappe
from frappe import _


def remove_broken_custom_blocks(doc, _event=None) -> None:
    """Drop Custom Block rows + corresponding content entries referencing missing HTML blocks."""

    if not getattr(doc, "custom_blocks", None):
        return

    removed_blocks: set[str] = set()
    for row in list(doc.custom_blocks):
        block_name = (row.custom_block_name or "").strip()
        if not block_name:
            continue

        if not frappe.db.exists("Custom HTML Block", block_name):
            doc.remove(row)
            removed_blocks.add(block_name)

    if not removed_blocks:
        return

    content = doc.content
    if content:
        try:
            layout = json.loads(content)
        except Exception:
            layout = []

        filtered = [
            block
            for block in layout
            if not (
                block.get("type") == "custom_block"
                and (block.get("data") or {}).get("custom_block_name") in removed_blocks
            )
        ]

        if len(filtered) != len(layout):
            doc.content = json.dumps(filtered, separators=(",", ":"))

    frappe.msgprint(
        _("Removed workspace cards that referenced deleted Custom HTML Blocks: {0}").format(
            ", ".join(sorted(removed_blocks))
        ),
        alert=True,
    )
