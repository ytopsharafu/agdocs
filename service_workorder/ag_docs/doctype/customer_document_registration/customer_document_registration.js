// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Document Registration", {
	async refresh(frm) {
		toggle_customer_field_visibility(frm);
		if (frm.doc.customer && (!frm.doc.customer_email || !frm.doc.customer_mobile)) {
			await auto_fetch_customer_contacts(frm);
		}
	},
	async customer(frm) {
		await auto_fetch_customer_contacts(frm, true);
	},
	after_save(frm) {
		toggle_customer_field_visibility(frm);
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

	// Ensure field stays visible even after save
	frm.set_df_property("customer", "hidden", 0);

	const readOnly = !frm.is_new();
	frm.set_df_property("customer", "read_only", readOnly ? 1 : 0);
}
