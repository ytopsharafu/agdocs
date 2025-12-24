"""Ensure latest fixtures (Client Scripts, Number Cards, etc.) are loaded."""

from __future__ import annotations

import frappe
from frappe.utils.fixtures import sync_fixtures


def execute() -> None:
    site = getattr(frappe.local, "site", "<unknown>")
    frappe.logger().info("Syncing service_workorder fixtures for site %s", site)
    sync_fixtures("service_workorder")
