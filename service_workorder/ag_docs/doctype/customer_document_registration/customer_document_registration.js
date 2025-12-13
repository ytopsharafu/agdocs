// Copyright (c) 2025, Mohamed Sharafudheen and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Document Registration", {
	async refresh(frm) {
		toggle_customer_field_visibility(frm);
		unlock_contact_fields(frm);

		await ensure_alert_days_for_all_rows(frm, { skip_if_present: true });
		await warn_existing_registration(frm);
		await refresh_document_number_warnings(frm);
		attach_document_number_listeners(frm);
		clear_place_of_issue_default(frm);
	},
	async customer(frm) {
		await warn_existing_registration(frm);
		if (!frm.is_new()) {
			return;
		}
		await auto_fetch_customer_contacts(frm, { force: true });
	},
	async document_details_add(frm, cdt, cdn) {
		clear_place_of_issue_default(frm);
		reset_place_of_issue(cdt, cdn);
		await set_alert_days_from_master(frm, cdt, cdn);
	},
	document_details_remove(frm) {
		refresh_document_number_warnings(frm);
	},
	async before_save(frm) {
		const is_unique = await enforce_unique_customer(frm);
		if (!is_unique) {
			return;
		}
		await confirm_save(frm);
		await ensure_alert_days_for_all_rows(frm);
	},
	after_save(frm) {
		toggle_customer_field_visibility(frm);
		unlock_contact_fields(frm);
		show_save_status(frm);
	},
});

frappe.ui.form.on("Document Detail", {
	async document_type(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},
	async document_number(frm, cdt, cdn) {
		await handle_document_number_change(frm, cdt, cdn);
	},
	place_of_issue(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row) {
			row.__manual_place_of_issue = true;
		}
	},
});

async function auto_fetch_customer_contacts(frm, options = {}) {
	const opts = typeof options === "boolean" ? { force: options } : options;
	const { force = false } = opts;

	if (frm.__contact_fetch_in_progress) {
		return;
	}

	if (!frm.doc.customer) {
		clear_customer_contact_fields(frm, true);
		return;
	}

	if (force) {
		clear_customer_contact_fields(frm);
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

		const email =
			message.contact_email ||
			message.customer_email ||
			message.email ||
			"";
		if (email && (force || !frm.doc.customer_email || frm.doc.customer_email !== email)) {
			updates.customer_email = email;
		}

		const mobile =
			message.contact_mobile ||
			message.mobile ||
			"";
		if (
			mobile &&
			(force || !frm.doc.customer_mobile || frm.doc.customer_mobile !== mobile)
		) {
			updates.customer_mobile = mobile;
		}

		apply_contact_updates(frm, updates);
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

async function warn_existing_registration(frm) {
	if (!frm.fields_dict.customer) {
		return;
	}

	if (!frm.doc.customer) {
		frm.__existing_registration = null;
		set_customer_warning(frm, "");
		return;
	}

	const currentCustomer = frm.doc.customer;

	try {
		const { message } = await frappe.call({
			method: "service_workorder.api.find_existing_document_registration",
			args: {
				customer: currentCustomer,
				exclude: frm.doc.name || "",
			},
		});

		if (currentCustomer !== frm.doc.customer) {
			return;
		}

		if (message && message.name) {
			frm.__existing_registration = message;
			const label = message.customer_name || message.customer || message.name;
			const safeLabel = frappe.utils.escape_html(label);
			const url = `/app/customer-document-registration/${message.name}`;
			const text = `<span class="text-danger">${__(
				"A registration already exists for {0}.",
				[safeLabel]
			)} <a href="${url}" target="_blank">${__("View record")}</a></span>`;
			set_customer_warning(frm, text);
		} else {
			frm.__existing_registration = null;
			set_customer_warning(frm, "");
		}
	} catch (err) {
		console.warn("Duplicate registration check failed", err);
		frm.__existing_registration = null;
		set_customer_warning(frm, "");
	}
}

async function enforce_unique_customer(frm) {
	if (!frm.doc.customer) {
		return true;
	}

	const existing = frm.__existing_registration;
	if (existing && existing.name) {
		const label = existing.customer_name || existing.customer || existing.name;
		frappe.validated = false;
		frappe.throw(
			__(
				"A document registration already exists for {0}. Please update the existing record instead.",
				[label]
			)
		);
		return false;
	}

	return true;
}

function set_customer_warning(frm, text) {
	if (!frm.fields_dict.customer) {
		return;
	}

	if (typeof frm.__customer_default_description === "undefined") {
		frm.__customer_default_description = frm.fields_dict.customer.df.description || "";
	}

	const value = text || frm.__customer_default_description || "";
	frm.set_df_property("customer", "description", value);
}

function apply_contact_updates(frm, updates) {
	const entries = Object.entries(updates || {}).filter(
		([, value]) => typeof value === "string" && value.trim()
	);

	if (!entries.length) {
		return;
	}

	entries.forEach(([fieldname, value]) => frm.set_value(fieldname, value));
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

	frm.set_df_property("customer", "hidden", 0);
	const readOnly = (frm.doc.docstatus || 0) > 0;
	frm.set_df_property("customer", "read_only", readOnly ? 1 : 0);
}

function reset_place_of_issue(cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row) return;
	if (row.__manual_place_of_issue) return;

	const defaultCountry = frappe.sys_defaults?.country || "";
	if (!row.place_of_issue || row.place_of_issue === defaultCountry) {
		frappe.model.set_value(cdt, cdn, "place_of_issue", "");
	}
}

async function set_alert_days_from_master(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row || !row.document_type) {
		frappe.model.set_value(cdt, cdn, "alert_days", "");
		frappe.model.set_value(cdt, cdn, "alert_repeat_interval", "");
		return;
	}

	try {
		const { message } = await frappe.db.get_value("Document Type Master", row.document_type, [
			"alert_days",
			"repeat_interval",
		]);

		if (message) {
			if (message.alert_days) {
				frappe.model.set_value(cdt, cdn, "alert_days", message.alert_days);
			}
			if (message.repeat_interval) {
				frappe.model.set_value(cdt, cdn, "alert_repeat_interval", message.repeat_interval);
			}
		}
	} catch (err) {
		console.error("Failed to fetch alert days", err);
	}
}

async function ensure_alert_days_for_all_rows(frm, opts = {}) {
	const rows = frm.doc.document_details || [];
	for (const row of rows) {
		if (opts.skip_if_present && row.alert_days) {
			continue;
		}
		await set_alert_days_from_master(frm, row.doctype || "Document Detail", row.name);
	}
}

async function confirm_save(frm) {
	if (frm.__save_confirmed) return;
	const question = frm.is_new()
		? __("Do you want to create this registration?")
		: __("Do you want to update this registration?");

	const confirmed = await new Promise((resolve) => {
		frappe.confirm(question, () => resolve(true), () => resolve(false));
	});

	if (!confirmed) {
		frappe.validated = false;
		frappe.show_alert({ message: __("Save cancelled"), indicator: "orange" });
		throw new Error("Save cancelled");
	}

	frm.__save_confirmed = true;
	frm.__was_new = frm.is_new();
}

function show_save_status(frm) {
	if (!frm.__save_confirmed) return;
	const message = frm.__was_new
		? __("Customer Document Registration created successfully.")
		: __("Customer Document Registration updated successfully.");
	frappe.show_alert({ message, indicator: "green" });
	frm.__save_confirmed = false;
}

function unlock_contact_fields(frm) {
	["customer_email", "customer_mobile"].forEach((fieldname) => {
		const df = frm.fields_dict[fieldname];
		if (df) {
			df.df.read_only = 0;
			frm.set_df_property(fieldname, "read_only", 0);
			const wrapper = df.$wrapper && df.$wrapper.find("input");
			if (wrapper && wrapper.length) {
				wrapper.prop("readonly", false).removeClass("input-disabled");
			}
			frm.refresh_field(fieldname);
		}
	});
}

function clear_place_of_issue_default(frm) {
	const grid = frm.fields_dict.document_details?.grid;
	if (!grid) {
		return;
	}
	const placeField = grid.fields_map?.place_of_issue;
	if (placeField && placeField.default) {
		placeField.default = "";
	}
}

function attach_document_number_listeners(frm) {
	if (frm.__document_number_listener_attached) {
		return;
	}

	const grid = frm.fields_dict.document_details?.grid;
	if (!grid) {
		return;
	}

	const handler = frappe.utils.debounce((target) => {
		const rowWrapper = $(target).closest(".grid-row");
		const gridRow = rowWrapper.data("grid_row");
		if (!gridRow || !gridRow.doc) {
			return;
		}
		handle_document_number_change(frm, gridRow.doc.doctype, gridRow.doc.name);
	}, 300);

	grid.wrapper.on("input", "[data-fieldname='document_number'] input", function () {
		handler(this);
	});

	frm.__document_number_listener_attached = true;
}

async function refresh_document_number_warnings(frm) {
	const rows = frm.doc.document_details || [];
	for (const row of rows) {
		if (!row.document_number) {
			set_document_number_warning(frm, row.name, "");
			continue;
		}
		await handle_document_number_change(frm, row.doctype || "Document Detail", row.name);
	}
}

async function handle_document_number_change(frm, cdt, cdn) {
	const row = frappe.get_doc(cdt, cdn);
	if (!row) return;

	const trimmed = (row.document_number || "").trim();
	set_document_number_warning(frm, cdn, "");
	row.__duplicate_warning_text = "";

	if (!trimmed) {
		return;
	}

	const duplicateRow = find_duplicate_row_in_form(frm, trimmed, cdn);
	if (duplicateRow) {
		const message = __("Same document number is already used in row #{0}.", [duplicateRow.idx || ""]);
		set_document_number_warning(frm, cdn, message);
		row.__duplicate_warning_text = message;
		return;
	}

	const requestId = Math.random().toString(36).slice(2);
	frm.__doc_number_checks = frm.__doc_number_checks || {};
	frm.__doc_number_checks[cdn] = requestId;

	try {
		const { message } = await frappe.call({
			method: "service_workorder.api.find_document_number_usage",
			args: {
				document_number: trimmed,
				parent: frm.doc.name || "",
				parenttype: frm.doctype,
				rowname: row.name || "",
			},
		});

		if (frm.__doc_number_checks[cdn] !== requestId) {
			return;
		}

		if (message && message.parent) {
			const note =
				message.parenttype === frm.doctype && message.parent === frm.doc.name
					? __("This document number exists in another row of this record.")
					: __(
							"Document number already exists in {0} ({1}).",
							[frappe.utils.escape_html(message.parent), message.parenttype]
					  );

			set_document_number_warning(frm, cdn, note);
			row.__duplicate_warning_text = note;
		} else {
			set_document_number_warning(frm, cdn, "");
			row.__duplicate_warning_text = "";
		}
	} catch (err) {
		console.warn("Document number validation failed", err);
	}
}

function find_duplicate_row_in_form(frm, number, currentCdn) {
	const rows = frm.doc.document_details || [];
	const normalized = number.trim().toLowerCase();

	for (const row of rows) {
		if (!row.document_number) continue;
		if (row.name === currentCdn) continue;

		if (row.document_number.trim().toLowerCase() === normalized) {
			return row;
		}
	}

	return null;
}

function set_document_number_warning(frm, cdn, message) {
	const grid = frm.fields_dict.document_details?.grid;
	if (!grid) return;
	const row = grid.grid_rows_by_docname[cdn];
	if (!row) return;

	const cell = row.wrapper.find("[data-fieldname='document_number']").first();
	if (!cell.length) {
		return;
	}

	let holder = cell.find(".document-number-warning-holder");
	if (!holder.length) {
		holder = $('<div class="document-number-warning-holder mt-1"></div>').appendTo(cell);
	}

	if (message) {
		holder.html(`<div class="document-number-warning text-danger small">${message}</div>`);
	} else {
		holder.empty();
	}
}
