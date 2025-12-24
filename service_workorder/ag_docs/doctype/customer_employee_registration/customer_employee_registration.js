frappe.ui.form.on("Customer Employee Registration", {
	async refresh(frm) {
		setup_save_confirmation(frm);

		frm.set_query("dep_emp_name", () => {
			if (frm.doc.employee_type !== "Dependent") {
				return {};
			}

			if (!frm.doc.customer_name) {
				frappe.msgprint(__("Please select a Customer first"));
				return { filters: { name: ["is", "set"] } };
			}

			return {
				filters: {
					customer_name: frm.doc.customer_name,
					employee_type: "Employee",
					active: 1,
				},
			};
		});

		if (frm.is_new()) {
			frm.set_value("nationality", "");
		}

		await ensure_uid_limits_loaded(frm, true);
		await enforce_dep_no_requirement(frm);
		apply_uid_requirement(frm);

		await ensure_alert_days_for_all_rows(frm, { skip_if_present: true });
	},

	async customer_name(frm) {
		frm.set_value("dep_emp_name", "");
		frm.set_value("linked_emp_info", "");
		await enforce_dep_no_requirement(frm);
	},

	employee_type(frm) {
		frm.set_value("dep_emp_name", "");
		frm.set_value("linked_emp_info", "");
	},

	new_employee(frm) {
		apply_uid_requirement(frm);
	},

	async dep_emp_name(frm) {
		if (!frm.doc.dep_emp_name) {
			frm.set_value("linked_emp_info", "");
			return;
		}

		try {
			const emp = await frappe.db.get_doc("Customer Employee Registration", frm.doc.dep_emp_name);
			const asText = (v) => ((v === undefined || v === null) ? "" : String(v).trim());

			const depNo1 = asText(emp.dep_no1 || emp.dep_no_1 || emp.department_no1 || emp.department_no_1);
			const depNo2 = asText(emp.dep_no2 || emp.dep_no_2 || emp.department_no2 || emp.department_no_2);
			const deptText = [depNo1, depNo2].filter(Boolean).join(" / ");
			const eidText = asText(emp.eid_no);

			let info = "";
			if (deptText) info += `Dept: ${deptText}`;
			if (eidText) info += `${info ? " | " : ""}EID: ${eidText}`;
			frm.set_value("linked_emp_info", info || "");
		} catch (e) {
			console.error("Failed to load employee:", e);
			frm.set_value("linked_emp_info", "");
		}
	},

	uid_no(frm) {
		const allowBlank = !!cint(frm.doc.new_employee);
		const valid = validate_uid_input(frm, { allow_blank: allowBlank });
		if (valid && frm.doc.uid_no) {
			frm.set_value("new_employee", 0);
		}
	},

	validate(frm) {
		const allowBlank = !!cint(frm.doc.new_employee);
		const valid = validate_uid_input(frm, { allow_blank: allowBlank, focus: true });
		if (!valid) {
			frappe.validated = false;
		}
	},

	first_name(frm) {
		validate_name_field(frm, "first_name");
	},

	last_name(frm) {
		validate_name_field(frm, "last_name");
	},

	async document_details_add(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Document Detail", {
	async document_type(frm, cdt, cdn) {
		await set_alert_days_from_master(frm, cdt, cdn);
	},

	override_alert_settings(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row && !row.override_alert_settings) {
			set_alert_days_from_master(frm, cdt, cdn);
		}
	},
});

const UID_LIMIT_DEFAULTS = { min: 5, max: 15 };
const UID_INLINE_CLASS = "uid-inline-warning";

function get_active_uid_limits(frm) {
	return (frm && frm.__uid_limits) || UID_LIMIT_DEFAULTS;
}

async function ensure_uid_limits_loaded(frm, force = false) {
	if (!frm) {
		return UID_LIMIT_DEFAULTS;
	}

	if (!force && frm.__uid_limits) {
		return frm.__uid_limits;
	}

	try {
		const response = await frappe.call({
			method: "service_workorder.service_workorder.api.get_uid_length_limits",
			freeze: false,
		});

		const payload = response.message || {};
		const minLength = cint(payload.min) || UID_LIMIT_DEFAULTS.min;
		const maxLength = cint(payload.max) || UID_LIMIT_DEFAULTS.max;

		frm.__uid_limits = {
			min: Math.max(1, minLength),
			max: Math.max(Math.max(1, minLength), maxLength),
		};
	} catch (err) {
		console.error("Failed to load UID length limits:", err);
		frm.__uid_limits = UID_LIMIT_DEFAULTS;
	}

	return frm.__uid_limits;
}

function set_uid_inline_message(frm, message) {
	const field = frm.fields_dict?.uid_no;
	if (!field || !field.$wrapper) {
		return;
	}

	let note = field.$wrapper.find(`.${UID_INLINE_CLASS}`);
	if (!message) {
		note.remove();
		return;
	}

	if (!note.length) {
		note = $("<div></div>").addClass(`${UID_INLINE_CLASS}`);
		note.css({
			"font-size": "12px",
			"margin-top": "4px",
			color: "#c0341d",
		});
		field.$wrapper.append(note);
	}

	note.text(message);
}

function focus_uid_field(frm) {
	const field = frm.fields_dict?.uid_no;
	if (!field || !field.$wrapper) {
		return;
	}
	const wrapper = field.$wrapper.get(0);
	if (wrapper && wrapper.scrollIntoView) {
		wrapper.scrollIntoView({ behavior: "smooth", block: "center" });
	}
	if (field.$input && field.$input.length) {
		field.$input.focus();
	}
}

async function enforce_dep_no_requirement(frm) {
	const customer = frm.doc.customer_name;

	if (!customer) {
		apply_dep_no_requirement(frm, false);
		frm.__dep_no_customer_flag = null;
		return;
	}

	if (frm.__dep_no_customer_flag && frm.__dep_no_customer_flag.customer === customer) {
		apply_dep_no_requirement(frm, frm.__dep_no_customer_flag.required);
		return;
	}

	try {
		const { message } = await frappe.db.get_value("Customer", customer, "custom_emp_dep_id");
		const required = cint(message?.custom_emp_dep_id) === 1;
		frm.__dep_no_customer_flag = { customer, required };
		apply_dep_no_requirement(frm, required);
	} catch (e) {
		console.error("Failed to check Emp Dep ID flag:", e);
		apply_dep_no_requirement(frm, false);
	}
}

function apply_dep_no_requirement(frm, required) {
	const needsDepNo = Boolean(required);

	frm.toggle_reqd("dep_no1", needsDepNo);
	frm.toggle_reqd("dep_no2", needsDepNo);

	frm.set_df_property("dep_no", "read_only", needsDepNo ? 1 : 0);
	frm.set_df_property(
		"dep_no",
		"description",
		needsDepNo ? __("Required because Emp Dep ID is enabled for this customer.") : ""
	);

	if (needsDepNo && !frm.doc.dep_no) {
		frm.set_value("dep_no", 1);
	}
}

function apply_uid_requirement(frm) {
	const uidRequired = !cint(frm.doc.new_employee);

	frm.toggle_reqd("uid_no", uidRequired);
	frm.set_df_property(
		"uid_no",
		"description",
		uidRequired ? "" : __("UID not required while New Employee is enabled.")
	);

	validate_uid_input(frm, { allow_blank: !uidRequired });
}

function setup_save_confirmation(frm) {
	if (frm.__save_interceptor_attached) {
		return;
	}

	const originalSave = frm.save.bind(frm);

	frm.save = function (...args) {
		if (frm.doc.docstatus !== 0 || frm.__skip_save_confirm) {
			return originalSave(...args);
		}

		const isInsert = frm.is_new();

		return new Promise((resolve, reject) => {
			const proceed = (choice) => {
				frm.__post_save_choice = choice;
				frm.__skip_save_confirm = true;
				Promise.resolve(originalSave(...args))
					.then(resolve)
					.catch(reject)
					.finally(() => {
						frm.__skip_save_confirm = false;
					});
			};

			const cancel = () => {
				frm.__post_save_choice = "cancelled";
				resolve();
			};

			if (isInsert) {
				frappe.confirm(
					__("Save this record and create another?"),
					() => proceed("new"),
					() => proceed("stay")
				);
			} else {
				frappe.confirm(
					__("Do you want to update this record?"),
					() => proceed("update"),
					cancel
				);
			}
		});
	};

	frm.__save_interceptor_attached = true;
}

function validate_uid_input(frm, options = {}) {
	const value = (frm.doc.uid_no || "").trim();
	const allowBlank = Boolean(options.allow_blank);

	if (!value) {
		if (allowBlank) {
			set_uid_inline_message(frm, "");
			frm.__uid_error = null;
			return true;
		}
		const message = __("UID Number is required.");
		set_uid_inline_message(frm, message);
		frm.__uid_error = message;
		if (options.focus) {
			focus_uid_field(frm);
		}
		return false;
	}

	const limits = get_active_uid_limits(frm);
	const error = get_uid_error(value, limits);
	if (error) {
		set_uid_inline_message(frm, error);
		frm.__uid_error = error;
		if (options.focus) {
			focus_uid_field(frm);
		}
		return false;
	}

	set_uid_inline_message(frm, "");
	frm.__uid_error = null;
	return true;
}

function get_uid_error(value, limits = UID_LIMIT_DEFAULTS) {
	if (!/^\d+$/.test(value)) {
		return __("UID must contain digits only.");
	}

	const minLength = Math.max(1, cint((limits && limits.min) || UID_LIMIT_DEFAULTS.min));
	const maxLength = Math.max(minLength, cint((limits && limits.max) || UID_LIMIT_DEFAULTS.max));

	if (value.length < minLength || value.length > maxLength) {
		return __("UID must be between {0} and {1} digits.", [minLength, maxLength]);
	}

	if (/^(\d)\1+$/.test(value)) {
		return __("UID cannot be the same digit repeated.");
	}

	if (is_sequential_digits(value)) {
		return __("UID cannot be a sequential number.");
	}

	return "";
}

function is_sequential_digits(value) {
	const digits = value.split("").map((d) => parseInt(d, 10));
	const asc = digits.every((digit, idx) => idx === 0 || digit - digits[idx - 1] === 1);
	const desc = digits.every((digit, idx) => idx === 0 || digits[idx - 1] - digit === 1);
	return asc || desc;
}

function validate_name_field(frm, fieldname) {
	const raw = (frm.doc[fieldname] || "").trim();
	if (!raw) return;

	const error = get_name_error(raw);
	if (error) {
		frappe.msgprint({
			title: __("Invalid Name"),
			indicator: "red",
			message: error,
		});
		frm.set_value(fieldname, "");
	}
}

function get_name_error(value) {
	const lowered = value.toLowerCase();
	const plain = value.replace(/[^a-z]/gi, "");
	const blacklist = ["none", "other", "test", "dummy", "sample", "na", "n/a"];

	if (lowered.length < 2) {
		return __("Name is too short.");
	}

	if (blacklist.includes(lowered)) {
		return __("Placeholder names are not allowed.");
	}

	if (!plain) {
		return __("Name must include alphabetic characters.");
	}

	if (/^[\d\s]+$/.test(value)) {
		return __("Name cannot be numbers only.");
	}

	if (/^([a-z])\1+$/i.test(plain)) {
		return __("Name cannot be the same letter repeated.");
	}

	if (!/[aeiouy]/i.test(plain)) {
		return __("Name must contain a vowel.");
	}

	return "";
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
			frappe.model.set_value(cdt, cdn, "alert_days", message.alert_days || "");
			frappe.model.set_value(
				cdt,
				cdn,
				"alert_repeat_interval",
				message.repeat_interval || ""
			);
		}
	} catch (err) {
		console.error("Failed to fetch alert days for Document Detail", err);
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
