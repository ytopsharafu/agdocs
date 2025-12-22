"""
Ensure the custom dashboard cards remain compact on smaller displays.

The affected cards live inside Custom HTML Blocks and render inside a shadow DOM,
so the only safe way to adjust their appearance is by replacing the inline CSS
stored on the document itself.
"""

from __future__ import annotations

import frappe


RESPONSIVE_CARD_CSS = """@import url('/assets/service_workorder/css/icomoon/style.css');

:host [class^="icon-"],
:host [class*=' icon-'] {
    font-family: 'icomoon' !important;
    font-style: normal !important;
    font-weight: normal !important;
    line-height: 1 !important;
}

:host .custom-dashboard {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: stretch;
    gap: clamp(6px, 0.9vw, 14px);
    width: min(100%, 1000px);
    margin: 0 auto;
}

:host .dashboard-card {
    width: clamp(88px, 9vw, 132px);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    gap: clamp(4px, 0.8vw, 8px);
    padding: clamp(6px, 0.9vw, 12px);
    transition: transform 0.18s ease, color 0.18s ease;
    cursor: pointer;
    user-select: none;
    background: transparent;
    border: none;
    box-shadow: none;
}

:host .dashboard-icon {
    font-size: 34px !important;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6px;
}

:host .dashboard-title {
    font-size: clamp(11px, 1vw, 13px);
    font-weight: 600;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

@media (max-width: 1700px) {
    :host .dashboard-card {
        width: clamp(82px, 9vw, 120px);
    }
}

@media (max-width: 1200px) {
    :host .custom-dashboard {
        width: 100%;
        gap: clamp(6px, 1.6vw, 12px);
    }

    :host .dashboard-card {
        width: clamp(78px, 22vw, 108px);
    }
}

@media (max-width: 768px) {
    :host .dashboard-card {
        width: clamp(72px, 38vw, 100px);
    }
}

:host .dashboard-card:hover {
    transform: translateY(-3px);
}

/* light theme (default) */
:host .dashboard-icon {
    color: #1284e4 !important;
}

:host .dashboard-title {
    color: #1b1b1b;
}

:host .dashboard-card:hover .dashboard-icon {
    color: #0a6fcc !important;
}

:host .dashboard-card:hover .dashboard-title {
    color: #040404;
}

/* dark theme */
:host-context([data-theme='dark']) .dashboard-icon {
    color: #f5f5f5 !important;
}

:host-context([data-theme='dark']) .dashboard-title {
    color: #ffffff;
}

:host-context([data-theme='dark']) .dashboard-card:hover .dashboard-icon {
    color: #80bfff !important;
}

:host-context([data-theme='dark']) .dashboard-card:hover .dashboard-title {
    color: #dfe9ff;
}
"""


def execute() -> None:
    """Replace the CSS for every dashboard-style Custom HTML Block."""
    if not frappe.db.table_exists("Custom HTML Block"):
        return

    block_names = frappe.get_all(
        "Custom HTML Block",
        filters={"style": ["like", "%custom-dashboard%"]},
        pluck="name",
    )

    if not block_names:
        return

    for name in block_names:
        doc = frappe.get_doc("Custom HTML Block", name)
        if ".custom-dashboard" not in (doc.style or ""):
            continue

        doc.style = RESPONSIVE_CARD_CSS
        doc.save(ignore_permissions=True)
