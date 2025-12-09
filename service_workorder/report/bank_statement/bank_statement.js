frappe.query_reports["Bank Statement"] = {
	onload: function (report) {
		const defaultCompany = frappe.defaults.get_user_default("Company");
		if (defaultCompany && !frappe.query_report.get_filter_value("company")) {
			report.set_filter_value("company", defaultCompany);
		}

		const formatDate = (dateStr) => moment(dateStr).format(frappe.defaultDateFormat);
		let syncing_range = false;

		const setRange = (preset) => {
			if (!preset || preset === "Custom") {
				return;
			}

			const today = frappe.datetime.get_today();
			let from_date = formatDate(today);
			let to_date = formatDate(today);

			if (preset === "Last 30 Days") {
				from_date = formatDate(frappe.datetime.add_days(today, -30));
			} else if (preset === "This Month") {
				from_date = formatDate(frappe.datetime.month_start());
				to_date = formatDate(frappe.datetime.month_end());
			} else if (preset === "Last Month") {
				from_date = moment(frappe.datetime.month_start()).subtract(1, "month").format(frappe.defaultDateFormat);
				to_date = moment(frappe.datetime.month_end()).subtract(1, "month").format(frappe.defaultDateFormat);
			} else if (preset === "This Year") {
				from_date = formatDate(frappe.datetime.year_start());
				to_date = formatDate(frappe.datetime.year_end());
			} else if (preset === "Last Year") {
				from_date = moment(frappe.datetime.year_start())
					.subtract(1, "year")
					.format(frappe.defaultDateFormat);
				to_date = moment(frappe.datetime.year_end())
					.subtract(1, "year")
					.format(frappe.defaultDateFormat);
			}

			syncing_range = true;
			report.set_filter_value("from_date", from_date);
			report.set_filter_value("to_date", to_date);
			syncing_range = false;
		};

		const dateRangeFilter = report.get_filter("date_range");
		if (dateRangeFilter) {
			const currentPreset = frappe.query_report.get_filter_value("date_range");
			if (!currentPreset || currentPreset === "Custom") {
				report.set_filter_value("date_range", "Last 30 Days");
				setRange("Last 30 Days");
			} else {
				setRange(currentPreset);
			}

			dateRangeFilter.df.onchange = () => {
				const preset = frappe.query_report.get_filter_value("date_range");
				setRange(preset);
			};
		} else {
			setRange("Last 30 Days");
		}

		const attachCustomWatcher = (fieldname) => {
			const field = report.get_filter(fieldname);
			if (!field) return;
			const original = field.df.onchange;
			field.df.onchange = () => {
				const user_edit =
					field.$input && (field.$input.is(":focus") || document.activeElement === field.$input[0]);
				if (!syncing_range && user_edit) {
					report.set_filter_value("date_range", "Custom");
				}
				original && original.call(field);
			};

			setTimeout(() => {
				if (!field.$input) return;
				field.$input.on("change.manual input.manual", () => {
					if (!syncing_range) {
						report.set_filter_value("date_range", "Custom");
					}
				});
			}, 0);
		};

		attachCustomWatcher("from_date");
		attachCustomWatcher("to_date");

		const accountFilter = report.get_filter("account");
		if (accountFilter) {
			accountFilter.df.get_query = () => {
				const company = frappe.query_report.get_filter_value("company");
				const filters = {
					account_type: "Bank",
					is_group: 0,
				};
				if (company) {
					filters.company = company;
				}
				return { filters };
			};
			accountFilter.refresh();
		}
	},
};
