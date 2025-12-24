# Copyright (c) 2025, Mohamed Sharafudheen and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class DocumentAlertSettings(Document):
	def validate(self):
		self.validate_uid_lengths()

	def validate_uid_lengths(self):
		min_length = cint(self.uid_min_length) or 7
		max_length = cint(self.uid_max_length) or 15

		if min_length < 1:
			min_length = 1

		if max_length < min_length:
			frappe.throw(_("UID Maximum Length must be greater than or equal to the minimum length."))

		self.uid_min_length = min_length
		self.uid_max_length = max_length
