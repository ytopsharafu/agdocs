async function update_uid_hint_for_sales_doc(frm, employeeFieldname, uidFieldname) {
	const employeeField = frm.fields_dict?.[employeeFieldname];
	if (!employeeField || !employeeField.$wrapper) {
		return;
	}

	const employee = frm.doc[employeeFieldname];
	if (!employee) {
		set_sales_uid_hint(frm, employeeFieldname, "");
		return;
	}

	try {
		const { message } = await frappe.db.get_value(
			"Customer Employee Registration",
			employee,
			["new_employee", "uid_no"]
		);

		const isNewEmployee = cint(message?.new_employee) === 1;
		const hasUID = Boolean(frm.doc[uidFieldname] || message?.uid_no);
		const text = isNewEmployee && !hasUID
			? __("New Employee selected. Please update the UID No. once it is available.")
			: "";
		set_sales_uid_hint(frm, employeeFieldname, text);
	} catch (err) {
		console.warn("Failed to check new_employee flag", err);
		set_sales_uid_hint(frm, employeeFieldname, "");
	}
}

function set_sales_uid_hint(frm, fieldname, text) {
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

frappe.ui.form.on("Sales Order", {
	async refresh(frm) {
		await update_uid_hint_for_sales_doc(frm, "custom_employee", "custom_uid_no");
	},
	async custom_employee(frm) {
		await update_uid_hint_for_sales_doc(frm, "custom_employee", "custom_uid_no");
	},
});

frappe.ui.form.on("Sales Invoice", {
	async refresh(frm) {
		await update_uid_hint_for_sales_doc(frm, "custom_employee", "custom_uid_no");
	},
	async custom_employee(frm) {
		await update_uid_hint_for_sales_doc(frm, "custom_employee", "custom_uid_no");
	},
});
