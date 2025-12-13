from frappe.model.document import Document
from frappe.utils import now_datetime


class DocumentAlertLog(Document):
    """Stores a single scheduler snapshot for document alert sends."""

    def before_insert(self):
        if not self.log_time:
            self.log_time = now_datetime()

        if not self.status:
            self.status = self._infer_status()

    def _infer_status(self):
        email_sent = int(self.emails_sent or 0)
        sms_sent = int(self.sms_sent or 0)
        email_failed = int(self.emails_failed or 0)
        sms_failed = int(self.sms_failed or 0)

        found_success = (email_sent + sms_sent) > 0
        found_failure = (email_failed + sms_failed) > 0

        if found_failure and not found_success:
            return "Failed"
        if found_failure and found_success:
            return "Partial Failures"
        if not found_success and not found_failure:
            return "Skipped"
        return "Success"
