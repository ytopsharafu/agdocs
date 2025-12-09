// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

const SERVICE_REQUEST_OPTIONAL_COLUMNS = [
	{ value: "payment_type", label: __("Payment Type") },
	{ value: "item_status", label: __("Item Status") },
	{ value: "item_date", label: __("Item Date") },
	{ value: "company", label: __("Company") },
	{ value: "tax_category", label: __("Tax Category") },
	{ value: "sales_taxes_and_charges_template", label: __("Tax Template") },
];

const SERVICE_REQUEST_STATUS_OPTIONS = [
	{ value: "Draft", label: __("Draft") },
	{ value: "Submitted", label: __("Submitted") },
	{ value: "Cancelled", label: __("Cancelled") },
];

const SERVICE_REQUEST_SORT_OPTIONS = [
	{ value: "", label: __("Default (Date Desc)") },
	{ value: "date", label: __("Document Date") },
	{ value: "item_date", label: __("Item Date") },
	{ value: "customer", label: __("Customer") },
	{ value: "employee", label: __("Employee Name") },
	{ value: "dep_no", label: __("Dep No") },
	{ value: "employee_type", label: __("Emp Type") },
	{ value: "item", label: __("Item") },
	{ value: "item_group", label: __("Item Group") },
	{ value: "owner", label: __("Created By") },
	{ value: "gov_charge", label: __("Gov Charge") },
	{ value: "service_charge", label: __("Service Charge") },
	{ value: "amount", label: __("Amount") },
];

const SERVICE_REQUEST_DUPLICATE_FIELDS = [
	"id",
	"service_request_count",
	"status",
	"date",
	"item_date",
	"customer",
	"employee",
	"dep_no",
	"employee_type",
	"item_group",
	"owner",
];

frappe.query_reports["Service Request Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "date_based_on",
			label: __("Date Based On"),
			fieldtype: "Select",
			options: "Document Date\nItem Date",
			default: "Document Date",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				const search = (txt || "").toLowerCase();
				return SERVICE_REQUEST_STATUS_OPTIONS.filter((option) =>
					!search || option.label.toLowerCase().includes(search)
				).map((option) => ({
					value: option.value,
					description: option.label,
				}));
			},
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "service_request_id",
			label: __("Service Request"),
			fieldtype: "Link",
			options: "Service Request",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			on_change(report) {
				frappe.query_report.set_filter_value("employee", "");
				report.refresh();
			},
		},
		{
			fieldname: "employee",
			label: __("Employee / Dependent"),
			fieldtype: "Link",
			options: "Customer Employee Registration",
			get_query() {
				const customer = frappe.query_report.get_filter_value("customer");
				if (customer) {
					return {
						filters: { customer_name: customer },
					};
				}
				return {};
			},
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "owner",
			label: __("Created By"),
			fieldtype: "Link",
			options: "User",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "additional_columns",
			label: __("Additional Columns"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				const search = (txt || "").toLowerCase();
				return SERVICE_REQUEST_OPTIONAL_COLUMNS.filter((col) =>
					!search || col.label.toLowerCase().includes(search)
				).map((col) => ({
					value: col.value,
					description: col.label,
				}));
			},
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "sort_by",
			label: __("Sort Column"),
			fieldtype: "Select",
			options: SERVICE_REQUEST_SORT_OPTIONS,
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "sort_order",
			label: __("Sort Order"),
			fieldtype: "Select",
			options: [
				{ label: __("Descending"), value: "DESC" },
				{ label: __("Ascending"), value: "ASC" },
			],
			default: "DESC",
			on_change(report) {
				report.refresh();
			},
		},
		{
			fieldname: "limit_page",
			label: __("Show Entries"),
			fieldtype: "Select",
			options: "20\n100\n500\n1500\n5000",
			default: "500",
			on_change(report) {
				const currentPage = frappe.query_report.get_filter_value("page");
				if (currentPage !== 1) {
					frappe.query_report.set_filter_value("page", 1);
				} else {
					report.refresh();
				}
			},
		},
		{
			fieldname: "page",
			label: __("Page"),
			fieldtype: "Int",
			default: 1,
			hidden: 1,
		},
		{
			fieldname: "page_len",
			label: __("Page Length"),
			fieldtype: "Int",
			default: 20,
			hidden: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const is_duplicate_row = row && row._is_duplicate;
		const is_total_row = row && row.is_total_row;
		const should_hide =
			(!is_total_row && is_duplicate_row && SERVICE_REQUEST_DUPLICATE_FIELDS.includes(column.fieldname));

		if (should_hide) {
			return "";
		}

		const formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname === "id" && value && !is_total_row) {
			return `<span class="font-weight-bold">${formatted_value}</span>`;
		}

		if (is_total_row) {
			return `<span class="font-weight-bold">${formatted_value || ""}</span>`;
		}

		return formatted_value;
	},

	onload(report) {
		add_report_utilities(report);
		apply_filter_widths(report);
	},
};

function add_report_utilities(report) {
	if (report.page.__sr_buttons_applied) {
		return;
	}

	report.page.__sr_buttons_applied = true;

	report.page.add_inner_button(__("Clear Filters"), function () {
		frappe.query_report.set_filter_value({
			from_date: "",
			to_date: "",
			date_based_on: "Document Date",
			status: [],
			service_request_id: "",
			customer: "",
			employee: "",
			item: "",
			item_group: "",
			owner: "",
			additional_columns: [],
			sort_by: "",
			sort_order: "DESC",
			limit_page: "500",
			page: 1,
			page_len: 20,
		});
		frappe.query_report.refresh();
	});

	report.page.add_inner_button(__("Previous"), function () {
		let page = frappe.query_report.get_filter_value("page");
		if (page > 1) {
			frappe.query_report.set_filter_value("page", page - 1);
			frappe.query_report.refresh();
		}
	});

	report.page.add_inner_button(__("Next"), function () {
		let page = frappe.query_report.get_filter_value("page");
		frappe.query_report.set_filter_value("page", page + 1);
		frappe.query_report.refresh();
	});
}

function apply_filter_widths(report) {
	const widths = {
		from_date: 150,
		to_date: 150,
		date_based_on: 190,
		status: 220,
		service_request_id: 220,
		customer: 280,
		employee: 260,
		item: 250,
		item_group: 200,
		owner: 200,
		additional_columns: 260,
		sort_by: 200,
		sort_order: 140,
		limit_page: 140,
	};

	Object.entries(widths).forEach(([fieldname, width]) => {
		const control = report.page.fields_dict[fieldname];
		if (!control || !control.$wrapper) return;
		control.$wrapper.css({
			flex: `0 0 ${width}px`,
			maxWidth: `${width}px`,
			minWidth: `${width}px`,
		});
	});
}
