frappe.ui.form.on('Document Detail', {
	place_of_issue(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		const defaultCountry = frappe.sys_defaults?.country || '';
		if (row.place_of_issue === defaultCountry) {
			frappe.model.set_value(cdt, cdn, 'place_of_issue', '');
		}
	}
});
