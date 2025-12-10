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
    height: clamp(88px, 9vw, 132px);
    border-radius: 18px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: clamp(10px, 0.9vw, 16px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    cursor: pointer;
    user-select: none;
}

:host .dashboard-icon {
    font-size: clamp(24px, 2.6vw, 38px) !important;
    margin-bottom: 6px;
}

:host .dashboard-title {
    font-size: clamp(12px, 1.15vw, 15px);
    font-weight: 600;
    line-height: 1.25;
}

@media (max-width: 1700px) {
    :host .dashboard-card {
        width: clamp(82px, 9vw, 120px);
        height: clamp(82px, 9vw, 120px);
    }
}

@media (max-width: 1200px) {
    :host .custom-dashboard {
        width: 100%;
        gap: clamp(6px, 1.6vw, 12px);
    }

    :host .dashboard-card {
        width: clamp(78px, 22vw, 108px);
        height: clamp(78px, 22vw, 108px);
    }
}

@media (max-width: 768px) {
    :host .dashboard-card {
        width: clamp(72px, 38vw, 100px);
        height: clamp(72px, 38vw, 100px);
    }
}

/* light theme (default) */
:host .dashboard-card {
    background: #f1f7ff;
    border: 1px solid #d5e3ff;
    color: #1b1b1b;
    box-shadow: none;
}

:host .dashboard-card:hover {
    transform: translateY(-3px);
    background: #e5efff;
    border-color: #c0d7ff;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}

:host .dashboard-icon {
    color: #1284e4 !important;
}

:host .dashboard-title {
    color: #1b1b1b;
}

/* dark theme */
:host-context([data-theme='dark']) .dashboard-card {
    background: #111214;
    border: 1px solid #25262b;
    color: #f3f3f3;
    box-shadow: none;
}

:host-context([data-theme='dark']) .dashboard-card:hover {
    background: #1a1b1f;
    border-color: #3a3b42;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.55);
}

:host-context([data-theme='dark']) .dashboard-icon {
    color: #f5f5f5 !important;
}

:host-context([data-theme='dark']) .dashboard-title {
    color: #ffffff;
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
