// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Document Registration", {
	async refresh(frm) {
		toggle_customer_field_visibility(frm);
		unlock_contact_fields(frm);

		if (frm.doc.customer && (!frm.doc.customer_email || !frm.doc.customer_mobile)) {
			await auto_fetch_customer_contacts(frm);
		}

		await ensure_alert_days_for_all_rows(frm, { skip_if_present: true });
	},
	async customer(frm) {
		await auto_fetch_customer_contacts(frm, true);
	},
	async document_details_add(frm, cdt, cdn) {
		reset_place_of_issue(cdt, cdn);
		await set_alert_days_from_master(frm, cdt, cdn);
	},
	async before_save(frm) {
		await confirm_save(frm);
		await ensure_alert_days_for_all_rows(frm);
	},
	after_save(frm) {
		toggle_customer_field_visibility(frm);
		unlock_contact_fields(frm);
		show_save_status(frm);
	},
});

frappe.ui.form.on("Document Detail", {
	async document_type(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},
	place_of_issue(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row) {
			row.__manual_place_of_issue = true;
		}
	},
});

async function auto_fetch_customer_contacts(frm, force = false) {
	if (frm.__contact_fetch_in_progress) {
		return;
	}

	if (!frm.doc.customer) {
		clear_customer_contact_fields(frm, true);
		return;
	}

	if (force) {
		clear_customer_contact_fields(frm);
	} else if (frm.doc.customer_email && frm.doc.customer_mobile) {
		return;
	}

	frm.__contact_fetch_in_progress = true;
	try {
		const currentCustomer = frm.doc.customer;
		const { message } = await frappe.call({
			method: "service_workorder.api.get_customer_contact_info",
			args: { customer: currentCustomer },
		});

		if (!message || currentCustomer !== frm.doc.customer) {
			return;
		}

		const updates = {};

		if (message.customer_name && message.customer_name !== frm.doc.customer_name) {
			updates.customer_name = message.customer_name;
		}

		const email = message.customer_email || message.email || "";
		if (email && (force || !frm.doc.customer_email)) {
			updates.customer_email = email;
		}

		const mobile = message.mobile || message.contact_mobile || "";
		if (mobile && (force || !frm.doc.customer_mobile || frm.doc.customer_mobile !== mobile)) {
			updates.customer_mobile = mobile;
		}

		for (const [fieldname, value] of Object.entries(updates)) {
			if (value) {
				frm.set_value(fieldname, value);
			}
		}
	} catch (err) {
		console.error("Auto-fetch contacts failed", err);
		frappe.msgprint({
			title: __("Contact Fetch Failed"),
			indicator: "red",
			message: __("Unable to fetch contact details for customer {0}", [frm.doc.customer]),
		});
	} finally {
		frm.__contact_fetch_in_progress = false;
	}
}

function clear_customer_contact_fields(frm, include_name = false) {
	const fields = ["customer_email", "customer_mobile"];
	if (include_name) {
		fields.push("customer_name");
	}

	fields.forEach((field) => {
		if (frm.doc[field]) {
			frm.set_value(field, "");
		}
	});
}

function toggle_customer_field_visibility(frm) {
	if (!frm.fields_dict.customer) {
		return;
	}

	frm.set_df_property("customer", "hidden", 0);
	const readOnly = !frm.is_new();
	frm.set_df_property("customer", "read_only", readOnly ? 1 : 0);
}

function reset_place_of_issue(cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row) return;
	if (row.__manual_place_of_issue) return;

	const defaultCountry = frappe.sys_defaults?.country || "";
	if (!row.place_of_issue || row.place_of_issue === defaultCountry) {
		frappe.model.set_value(cdt, cdn, "place_of_issue", "");
	}
}

async function set_alert_days_from_master(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row || !row.document_type) {
		frappe.model.set_value(cdt, cdn, "alert_days", "");
		return;
	}

	try {
		const { message } = await frappe.db.get_value("Document Type Master", row.document_type, "alert_days");
		if (message?.alert_days) {
			frappe.model.set_value(cdt, cdn, "alert_days", message.alert_days);
		}
	} catch (err) {
		console.error("Failed to fetch alert days", err);
	}
}

async function ensure_alert_days_for_all_rows(frm, opts = {}) {
	const rows = frm.doc.document_details || [];
	for (const row of rows) {
		if (opts.skip_if_present && row.alert_days) {
			continue;
		}
		await set_alert_days_from_master(frm, row.doctype || "Document Detail", row.name);
	}
}

async function confirm_save(frm) {
	if (frm.__save_confirmed) return;
	const question = frm.is_new()
		? __("Do you want to create this registration?")
		: __("Do you want to update this registration?");

	const confirmed = await new Promise((resolve) => {
		frappe.confirm(question, () => resolve(true), () => resolve(false));
	});

	if (!confirmed) {
		frappe.validated = false;
		frappe.show_alert({ message: __("Save cancelled"), indicator: "orange" });
		throw new Error("Save cancelled");
	}

	frm.__save_confirmed = true;
	frm.__was_new = frm.is_new();
}

function show_save_status(frm) {
	if (!frm.__save_confirmed) return;
	const message = frm.__was_new
		? __("Customer Document Registration created successfully.")
		: __("Customer Document Registration updated successfully.");
	frappe.show_alert({ message, indicator: "green" });
	frm.__save_confirmed = false;
}

function unlock_contact_fields(frm) {
	["customer_email", "customer_mobile"].forEach((fieldname) => {
		const df = frm.fields_dict[fieldname];
		if (df) {
			df.df.read_only = 0;
			frm.set_df_property(fieldname, "read_only", 0);
			const wrapper = df.$wrapper && df.$wrapper.find("input");
			if (wrapper && wrapper.length) {
				wrapper.prop("readonly", false).removeClass("input-disabled");
			}
			frm.refresh_field(fieldname);
		}
	});
}
