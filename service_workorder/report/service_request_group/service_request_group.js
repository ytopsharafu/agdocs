const SERVICE_REQUEST_OPTIONAL_COLUMNS = [
    { value: "payment_type", label: "Payment Type" },
    { value: "item_status", label: "Item Status" },
    { value: "item_date", label: "Item Date" },
    { value: "company", label: "Company" },
    { value: "tax_category", label: "Tax Category" },
    { value: "sales_taxes_and_charges_template", label: "Tax Template" }
];

frappe.query_reports["Service Request Group"] = {
    "filters": [
         {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date"
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date"
        },
        {
            "fieldname": "service_request_id",
            "label": "Service Request",
            "fieldtype": "Link",
            "options": "Service Request"
        },
        {
            "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "on_change": function(report) {
                const previousEmployee = frappe.query_report.get_filter_value("employee");
                if (previousEmployee) {
                    // Setting a new value triggers the employee filter's own refresh
                    frappe.query_report.set_filter_value("employee", "");
                } else {
                    // When nothing changes on employee we still need to refresh for the customer filter
                    report.refresh();
                }
            }
        },
        {
            "fieldname": "employee",
            "label": "Employee / Dependent",
            "fieldtype": "Link",
            "options": "Customer Employee Registration",
            get_query: function() {
                let customer = frappe.query_report.get_filter_value("customer");
                if (customer) {
                    return {
                        filters: {
                            customer_name: customer
                        }
                    };
                }
                return {};
            }
        },
        {
            "fieldname": "item",
            "label": "Item",
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "item_group",
            "label": "Item Group",
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "additional_columns",
            "label": "Additional Columns",
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                const search = (txt || "").toLowerCase();
                return SERVICE_REQUEST_OPTIONAL_COLUMNS
                    .filter(col => !search || col.label.toLowerCase().includes(search))
                    .map(col => ({ value: col.value, description: col.label }));
            },
            "on_change": function(report) {
                report.refresh();
            }
        },
        {
            "fieldname": "limit_page",
            "label": "Show Entries",
            "fieldtype": "Select",
            "options": "20\n100\n500\n1500\n5000",
            "default": "500",
            "on_change": function(report) {
                const currentPage = frappe.query_report.get_filter_value("page");
                if (currentPage !== 1) {
                    frappe.query_report.set_filter_value("page", 1);
                } else {
                    report.refresh();
                }
            }
        },
        {
            "fieldname": "page",
            "label": "Page",
            "fieldtype": "Int",
            "default": 1,
            "hidden": 1
        },
        {
            "fieldname": "page_len",
            "label": "Page Length",
            "fieldtype": "Int",
            "default": 20,
            "hidden": 1
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && data.is_total_row) {
            return `<span class="service-request-total">${value || ""}</span>`;
        }
        return value;
    },

    onload: function(report) {

    // Clear Filters
    report.page.add_inner_button("Clear Filters", function() {
        frappe.query_report.set_filter_value({
            customer: "",
            employee: "",
            service_request_id: "",
            item: "",
            item_group: "",
            additional_columns: [],
            from_date: "",
            to_date: "",
            limit_page: "500",
            page: 1,
            page_len: 20
        });
        frappe.query_report.refresh();
    });

    // Pagination
    report.page.add_inner_button("Previous", function() {
        let page = frappe.query_report.get_filter_value("page");
        if (page > 1) {
            frappe.query_report.set_filter_value("page", page - 1);
            frappe.query_report.refresh();
        }
    });

    report.page.add_inner_button("Next", function() {
        let page = frappe.query_report.get_filter_value("page");
        frappe.query_report.set_filter_value("page", page + 1);
        frappe.query_report.refresh();
    });

    // Filter widths need to be applied on the field wrappers themselves since
    // the query report filter row is a flex layout in v15.
    const filterWidths = {
        from_date: 150,
        to_date: 150,
        service_request_id: 250,
        customer: 350,
        employee: 300,
        item: 350,
        item_group: 200,
        additional_columns: 280,
        limit_page: 140
    };

    const applyFilterWidths = () => {
        Object.entries(filterWidths).forEach(([fieldname, width]) => {
            const control = report.page.fields_dict[fieldname];
            if (!control || !control.$wrapper) return;
            control.$wrapper.css({
                flex: `0 0 ${width}px`,
                maxWidth: `${width}px`,
                minWidth: `${width}px`
            });
        });
    };

    applyFilterWidths();

    if (!document.getElementById("service-request-group-style")) {
        const style = document.createElement("style");
        style.id = "service-request-group-style";
        style.textContent = `
            .service-request-total {
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
    }
},

};
