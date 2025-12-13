import frappe


def update_document_registration_contacts_from_customer(doc, _method=None):
    contact_name = doc.customer_primary_contact
    contact_details = _get_primary_contact(contact_name) if contact_name else {}

    updates = _collect_contact_updates(
        email=contact_details.get("email_id") or doc.email_id,
        mobile=contact_details.get("mobile") or doc.mobile_no or doc.phone,
    )
    if not updates:
        return

    registrants = _get_related_registrations(doc.name)
    if not registrants:
        return

    frappe.db.multiple_update(
        "Customer Document Registration",
        registrants,
        updates,
        update_modified=False,
    )


def update_document_registration_contacts_from_contact(doc, _method=None):
    if not (doc.is_primary_contact or doc.is_billing_contact):
        return

    customers = {
        link.link_name
        for link in getattr(doc, "links", [])
        if link.link_doctype == "Customer" and link.link_name
    }
    if not customers:
        return

    updates = _collect_contact_updates(
        email=doc.email_id,
        mobile=doc.mobile_no or doc.phone,
    )
    if not updates:
        return

    registrants = []
    for customer in customers:
        registrants.extend(_get_related_registrations(customer))

    if registrants:
        frappe.db.multiple_update(
            "Customer Document Registration",
            registrants,
            updates,
            update_modified=False,
        )


def _collect_contact_updates(email=None, mobile=None):
    updates = {}
    if email:
        updates["customer_email"] = email
    if mobile:
        updates["customer_mobile"] = mobile
    return updates


def _get_primary_contact(contact_name):
    if not contact_name:
        return {}

    try:
        contact = frappe.db.get_value(
            "Contact",
            contact_name,
            ["email_id", "mobile_no", "phone"],
            as_dict=True,
        ) or {}
    except Exception:
        return {}

    return {
        "email_id": contact.get("email_id"),
        "mobile": contact.get("mobile_no") or contact.get("phone"),
    }


def _get_related_registrations(customer):
    try:
        rows = frappe.get_all(
            "Customer Document Registration",
            filters={"customer": customer},
            pluck="name",
        )
    except Exception:
        rows = []
    return rows
