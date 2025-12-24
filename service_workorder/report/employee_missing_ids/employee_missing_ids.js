frappe.query_reports["Employee Missing IDs"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "employee_type",
			label: __("Employee Type"),
			fieldtype: "Select",
			options: "\nEmployee\nDependent",
		},
		{
			fieldname: "require_uid",
			label: __("Only Missing UID"),
			fieldtype: "Check",
		},
		{
			fieldname: "require_department",
			label: __("Only Missing Department No"),
			fieldtype: "Check",
		},
	],
};
