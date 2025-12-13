// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Request", {
	async refresh(frm) {
		await update_uid_hint_for_service_request(frm);
	},
	async dep_emp_name(frm) {
		await update_uid_hint_for_service_request(frm);
	},
});

async function update_uid_hint_for_service_request(frm) {
	const employeeFieldname = "dep_emp_name";
	const employeeField = frm.fields_dict?.[employeeFieldname];
	if (!employeeField || !employeeField.$wrapper) {
		return;
	}

	if (!frm.doc.dep_emp_name) {
		set_uid_hint(frm, employeeFieldname, "");
		return;
	}

	try {
		const { message } = await frappe.db.get_value(
			"Customer Employee Registration",
			frm.doc.dep_emp_name,
			["new_employee", "uid_no"]
		);
		const isNewEmployee = cint(message?.new_employee) === 1;
		const hasUID = Boolean(frm.doc.uid_no || message?.uid_no);
		const text =
			isNewEmployee && !hasUID
				? __("New Employee selected. Please update the UID No. once it is available.")
				: "";
		set_uid_hint(frm, employeeFieldname, text);
	} catch (err) {
		console.warn("Failed to fetch new_employee flag", err);
		set_uid_hint(frm, employeeFieldname, "");
	}
}

function set_uid_hint(frm, fieldname, text) {
	const field = frm.fields_dict?.[fieldname];
	if (!field || !field.$wrapper) {
		return;
	}

	const existing = field.$wrapper.find(".uid-reminder");
	if (!text) {
		existing.remove();
		return;
	}

	let label = existing;
	if (!label.length) {
		label = $('<div class="uid-reminder" style="font-size:12px;margin-top:4px;color:#c0341d;"></div>');
		field.$wrapper.append(label);
	}
	label.text(text);
}
