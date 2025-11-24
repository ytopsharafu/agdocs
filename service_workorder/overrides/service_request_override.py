import frappe
from frappe.model.document import Document

class ServiceRequestOverride(Document):

    def get_indicator(self):
        # Cancelled → always gray
        if self.docstatus == 2:
            return ("Cancelled", "gray", "")

        # All other statuses → remove green dot
        return ("", "gray", "")
