// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Alert Settings", {
	test_email(frm) {
		frm.call({
			method: "service_workorder.service_workorder.document_expiry.send_test_email",
		}).then((r) => {
			if (r.message) {
				frappe.msgprint(r.message);
			}
		});
	},

	test_sms(frm) {
		frm.call({
			method: "service_workorder.service_workorder.document_expiry.send_test_sms",
		}).then((r) => {
			if (r.message) {
				frappe.msgprint(r.message);
			}
		});
	},
});
