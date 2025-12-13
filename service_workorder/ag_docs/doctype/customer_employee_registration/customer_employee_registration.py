# Copyright (c) 2025, Mohamed Sharafudheen and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CustomerEmployeeRegistration(Document):
	def validate(self):
		self.ensure_uid_requirement()

	def ensure_uid_requirement(self):
		new_employee = frappe.utils.cint(self.get("new_employee"))
		if not new_employee and not self.uid_no:
			frappe.throw(
				_("UID No. is required unless the New Employee checkbox is enabled."),
				title=_("Missing UID")
			)
