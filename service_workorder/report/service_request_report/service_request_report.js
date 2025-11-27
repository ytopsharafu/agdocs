// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.query_reports["Service Request Report"] = {
	"filters": [

	]
};

frappe.query_reports["Service Request Report"] = {
    onload: function(report) {

        // ENABLE ADD COLUMN BUTTON
        report.page.add_inner_button("Add Column", function () {
            frappe.msgprint("To add a column, please edit report JSON or convert to a Query Report.");
        });

        // FORCE SHOW COLUMN MANAGER
        report.page.page.set_primary_action("Add Column", () => {
            report.show_column_picker = true;
            report.refresh();
        });

        // Ensure UI Supports Column Picker
        report.get_columns = function () {
            return report.columns;
        };
    }
};
