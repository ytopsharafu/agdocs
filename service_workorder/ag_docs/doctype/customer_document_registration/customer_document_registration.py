# Copyright (c) 2025, Mohamed Sharafudheen and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class CustomerDocumentRegistration(Document):
	def validate(self):
		self.ensure_unique_registration()
		self.ensure_unique_document_numbers()
		self.sync_customer_contacts()

	def ensure_unique_registration(self):
		if not self.customer:
			return

		filters = {
			"customer": self.customer,
			"docstatus": ("<", 2),
		}
		if self.name:
			filters["name"] = ("!=", self.name)

		existing = frappe.db.exists("Customer Document Registration", filters)
		if existing:
			link = get_link_to_form("Customer Document Registration", existing)
			frappe.throw(
				_("Customer {0} already has a document registration: {1}").format(
					frappe.bold(self.customer),
					link,
				),
				title=_("Duplicate Registration"),
			)

	def ensure_unique_document_numbers(self):
		if not (self.document_details or []):
			return

		seen = {}
		for row in self.document_details:
			number = (row.document_number or "").strip()
			if not number:
				continue

			key = number.lower()
			if key in seen:
				frappe.throw(
					_("Document number {0} is duplicated within this registration.").format(
						frappe.bold(number)
					),
					title=_("Duplicate Document Number"),
				)

			seen[key] = {
				"number": number,
				"rowname": row.name,
			}

		if not seen:
			return

		lookup_numbers = [data["number"] for data in seen.values()]
		lower_map = {number.lower(): number for number in lookup_numbers}

		placeholders = ", ".join(["%s"] * len(lower_map))
		existing = frappe.db.sql(
			f"""
			select
				name,
				parent,
				parenttype,
				document_number
			from `tabDocument Detail`
			where lower(document_number) in ({placeholders})
			""",
			tuple(lower_map.keys()),
			as_dict=True,
		)

		if not existing:
			return

		for row in existing:
			number = (row.get("document_number") or "").strip()
			key = number.lower()

			# Skip current document rows
			if (
				row.parenttype == self.doctype
				and row.parent == self.name
				and key in seen
				and seen[key]["rowname"]
				and row.name == seen[key]["rowname"]
			):
				continue

			parent_link = get_link_to_form(row.parenttype, row.parent)
			frappe.throw(
				_(
					"Document number {0} is already used in {1}."
				).format(frappe.bold(number), parent_link),
				title=_("Duplicate Document Number"),
			)

	def sync_customer_contacts(self):
		if not self.customer:
			return

		try:
			from service_workorder.api import get_customer_contact_info
		except Exception:
			return

		info = get_customer_contact_info(self.customer) or {}
		email = info.get("contact_email") or info.get("customer_email")
		mobile = info.get("contact_mobile") or info.get("mobile")

		if email and email != self.customer_email:
			self.customer_email = email

		if mobile and mobile != self.customer_mobile:
			self.customer_mobile = mobile
