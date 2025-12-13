frappe.ui.form.on("Customer Employee Registration", {
	refresh(frm) {
		ensure_alert_days_for_all_rows(frm, { skip_if_present: true });
	},
	async document_details_add(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Document Detail", {
	async document_type(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},
	override_alert_settings(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row && !row.override_alert_settings) {
			set_alert_days_from_master(frm, cdt, cdn);
		}
	},
});

async function set_alert_days_from_master(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row || !row.document_type) {
		frappe.model.set_value(cdt, cdn, "alert_days", "");
		frappe.model.set_value(cdt, cdn, "alert_repeat_interval", "");
		return;
	}

	try {
		const { message } = await frappe.db.get_value("Document Type Master", row.document_type, [
			"alert_days",
			"repeat_interval",
		]);

		if (message) {
			if (message.alert_days) {
				frappe.model.set_value(cdt, cdn, "alert_days", message.alert_days);
			} else {
				frappe.model.set_value(cdt, cdn, "alert_days", "");
			}
			if (message.repeat_interval) {
				frappe.model.set_value(cdt, cdn, "alert_repeat_interval", message.repeat_interval);
			} else {
				frappe.model.set_value(cdt, cdn, "alert_repeat_interval", "");
			}
		}
	} catch (err) {
		console.error("Failed to fetch alert days for Document Detail", err);
	}
}

async function ensure_alert_days_for_all_rows(frm, opts = {}) {
	const rows = frm.doc.document_details || [];
	for (const row of rows) {
		if (opts.skip_if_present && row.alert_days) {
			continue;
		}
		// await to keep ordering predictable
		await set_alert_days_from_master(frm, row.doctype || "Document Detail", row.name);
	}
}
