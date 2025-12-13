import frappe


SCRIPT_NAME = "main_emp_filter"
SCRIPT_CONTENT = """frappe.ui.form.on('Customer Employee Registration', {
    async refresh(frm) {
        setup_save_confirmation(frm);

        frm.set_query('dep_emp_name', () => {
            if (frm.doc.employee_type !== 'Dependent') return {};

            if (!frm.doc.customer_name) {
                frappe.msgprint(__('Please select a Customer first'));
                return { filters: { name: ['is', 'set'] } };
            }

            return {
                filters: {
                    customer_name: frm.doc.customer_name,
                    employee_type: 'Employee',
                    active: 1
                }
            };
        });

        if (frm.is_new()) {
            frm.set_value('nationality', '');
        }

        await enforce_dep_no_requirement(frm);
        apply_uid_requirement(frm);
    },

    async customer_name(frm) {
        frm.set_value('dep_emp_name', '');
        frm.set_value('linked_emp_info', '');
        await enforce_dep_no_requirement(frm);
    },

    employee_type(frm) {
        frm.set_value('dep_emp_name', '');
        frm.set_value('linked_emp_info', '');
    },

    new_employee(frm) {
        apply_uid_requirement(frm);
    },

    async dep_emp_name(frm) {
        if (!frm.doc.dep_emp_name) {
            frm.set_value('linked_emp_info', '');
            return;
        }

        try {
            const emp = await frappe.db.get_doc(
                'Customer Employee Registration',
                frm.doc.dep_emp_name
            );

            const asText = v => (v === undefined || v === null) ? '' : String(v).trim();

            const depNo1 = asText(emp.dep_no1 || emp.dep_no_1 || emp.department_no1 || emp.department_no_1);
            const depNo2 = asText(emp.dep_no2 || emp.dep_no_2 || emp.department_no2 || emp.department_no_2);

            const deptText = [depNo1, depNo2].filter(Boolean).join(' / ');
            const eidText = asText(emp.eid_no);

            let info = '';
            if (deptText) info += `Dept: ${deptText}`;
            if (eidText) info += `${info ? ' | ' : ''}EID: ${eidText}`;

            frm.set_value('linked_emp_info', info || '');
        } catch (e) {
            console.error('Failed to load employee:', e);
            frm.set_value('linked_emp_info', '');
        }
    },

    before_save(frm) {
        frm.__was_insert = frm.is_new();
    },

    async after_save(frm) {
        const justCreated = Boolean(frm.__was_insert);
        delete frm.__was_insert;

        const choice = frm.__post_save_choice || 'stay';
        frm.__post_save_choice = null;

        const defaultMessage = justCreated ? __('Saved Successfully') : __('Updated Successfully');
        const defaultIndicator = justCreated ? 'green' : 'blue';

        if (!justCreated) {
            if (choice === 'update') {
                frappe.show_alert({
                    message: defaultMessage,
                    indicator: defaultIndicator
                });
            }
            return;
        }

        if (choice === 'new') {
            frappe.show_alert({
                message: defaultMessage,
                indicator: defaultIndicator
            });
            await frappe.new_doc('Customer Employee Registration');
        } else {
            frappe.show_alert({
                message: __('Staying on current record'),
                indicator: 'blue'
            });
        }
    }
});


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
        const { message } = await frappe.db.get_value('Customer', customer, 'custom_emp_dep_id');
        const required = cint(message?.custom_emp_dep_id) === 1;
        frm.__dep_no_customer_flag = { customer, required };
        apply_dep_no_requirement(frm, required);
    } catch (e) {
        console.error('Failed to check Emp Dep ID flag:', e);
        apply_dep_no_requirement(frm, false);
    }
}

function apply_dep_no_requirement(frm, required) {
    const needsDepNo = Boolean(required);

    frm.toggle_reqd('dep_no1', needsDepNo);
    frm.toggle_reqd('dep_no2', needsDepNo);

    frm.set_df_property('dep_no', 'read_only', needsDepNo ? 1 : 0);
    frm.set_df_property(
        'dep_no',
        'description',
        needsDepNo ? __('Required because Emp Dep ID is enabled for this customer.') : ''
    );

    if (needsDepNo && !frm.doc.dep_no) {
        frm.set_value('dep_no', 1);
    }
}

function apply_uid_requirement(frm) {
    const uidRequired = !cint(frm.doc.new_employee);

    frm.toggle_reqd('uid_no', uidRequired);
    frm.set_df_property(
        'uid_no',
        'description',
        uidRequired ? '' : __('UID not required while New Employee is enabled.')
    );
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
                frm.__post_save_choice = 'cancelled';
                resolve();
            };

            if (isInsert) {
                frappe.confirm(
                    __('Save this record and create another?'),
                    () => proceed('new'),
                    () => proceed('stay')
                );
            } else {
                frappe.confirm(
                    __('Do you want to update this record?'),
                    () => proceed('update'),
                    cancel
                );
            }
        });
    };

    frm.__save_interceptor_attached = true;
}
"""


def execute():
    if frappe.db.exists("Client Script", SCRIPT_NAME):
        script_doc = frappe.get_doc("Client Script", SCRIPT_NAME)
        script_doc.script = SCRIPT_CONTENT
        script_doc.dt = "Customer Employee Registration"
        script_doc.enabled = 1
        script_doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Client Script",
                "dt": "Customer Employee Registration",
                "name": SCRIPT_NAME,
                "module": "Ag Docs",
                "view": "Form",
                "enabled": 1,
                "script": SCRIPT_CONTENT,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Customer Employee Registration")
