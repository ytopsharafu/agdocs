import frappe
from frappe import _
from frappe.model.document import Document


class ServiceRequestOverride(Document):
    def validate(self):
        self._ensure_payment_type_on_completed_rows()
        self._update_billing_status_field()

    def on_submit(self):
        self._update_billing_status_field()

    def on_update_after_submit(self):
        self._update_billing_status_field()

    def get_indicator(self):
        # Cancelled → always gray
        if self.docstatus == 2:
            return ("Cancelled", "gray", "")

        # All other statuses → remove green dot
        return ("", "gray", "")

    # -----------------------
    # Internal helpers
    # -----------------------
    def _ensure_payment_type_on_completed_rows(self):
        missing = []
        for row in self.work_details or []:
            status = (row.status or "").strip().lower()
            if status == "completed" and not row.payment_type:
                missing.append(str(row.idx or row.item_code or row.name))

        if missing:
            frappe.throw(
                _("Select Payment Type for completed rows: {0}").format(", ".join(missing))
            )

    def _update_billing_status_field(self):
        status = self._derive_billing_status()
        if status != self.get("billing_status"):
            self.billing_status = status

    def _derive_billing_status(self):
        if self.sales_invoice_ref:
            return "Invoiced"
        if self.sales_order_ref:
            return "Sales Order Created"

        rows = self.work_details or []
        if not rows:
            return "No Work Items"

        all_completed = all(
            (row.status or "").strip().lower() == "completed" for row in rows
        )

        if all_completed:
            return "Ready for Billing"

        return "In Progress"
