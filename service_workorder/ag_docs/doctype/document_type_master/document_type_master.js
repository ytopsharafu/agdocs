// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Type Master", {
	refresh(frm) {
		toggle_document_name_visibility(frm);
	},
	after_save(frm) {
		toggle_document_name_visibility(frm);
	},
});

function toggle_document_name_visibility(frm) {
	if (!frm.fields_dict.document_name) return;

	const readOnly = (frm.doc.docstatus || 0) > 0;
	frm.set_df_property("document_name", "read_only", readOnly ? 1 : 0);
}
