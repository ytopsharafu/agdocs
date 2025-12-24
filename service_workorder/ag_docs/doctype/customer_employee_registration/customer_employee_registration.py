# Copyright (c) 2025, Mohamed Sharafudheen and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CustomerEmployeeRegistration(Document):
	def validate(self):
		self.ensure_uid_requirement()
		self.ensure_unique_identity_values()

	def ensure_uid_requirement(self):
		new_employee = frappe.utils.cint(self.get("new_employee"))
		if not new_employee and not self.uid_no:
			frappe.throw(
				_("UID No. is required unless the New Employee checkbox is enabled."),
				title=_("Missing UID")
			)

	def ensure_unique_identity_values(self):
		for field in ("uid_no", "passport_no", "eid_no"):
			if not self._has_column(field):
				continue

			value = (self.get(field) or "").strip()
			if not value:
				continue

			existing = frappe.db.get_value(
				"Customer Employee Registration",
				{
					field: value,
					"name": ["!=", self.name],
				},
			)
			if existing:
				label = frappe.get_meta(self.doctype).get_label(field) or field.replace("_", " ").title()
				frappe.throw(
					_("{0} already exists in {1}. Please provide a unique value.").format(
						label, frappe.bold(existing)
					)
				)

	def _has_column(self, fieldname):
		try:
			return frappe.db.has_column(self.doctype, fieldname)
		except Exception:
			return False
