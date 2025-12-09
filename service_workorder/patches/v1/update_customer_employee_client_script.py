import frappe


SCRIPT_NAME = "main_emp_filter"
SCRIPT_CONTENT = """frappe.ui.form.on('Customer Employee Registration', {
    async refresh(frm) {
        // Only show main employees of the same customer when registering a dependent
        frm.set_query('dep_emp_name', () => {
            if (frm.doc.employee_type !== 'Dependent') return {};

            if (!frm.doc.customer_name) {
                frappe.msgprint(__('Please select a Customer first'));
                return { filters: { name: ['is', 'set'] } };
            }

            return {
                filters: {
                    customer_name: frm.doc.customer_name,
                    employee_type: 'Employee'
                }
            };
        });

        // Reset nationality only for brand new documents
        if (frm.is_new()) {
            frm.set_value('nationality', '');
        }

        await enforce_dep_no_requirement(frm);
    },

    async customer_name(frm) {
        // Clear dependent and linked info when customer changes
        frm.set_value('dep_emp_name', '');
        frm.set_value('linked_emp_info', '');
        await enforce_dep_no_requirement(frm);
    },

    employee_type(frm) {
        // Clear dependent and linked info when employee type changes
        frm.set_value('dep_emp_name', '');
        frm.set_value('linked_emp_info', '');
    },

    async dep_emp_name(frm) {
        // Load linked employee info when dependent employee is selected
        if (!frm.doc.dep_emp_name) {
            frm.set_value('linked_emp_info', '');
            return;
        }

        try {
            const emp = await frappe.db.get_doc(
                'Customer Employee Registration',
                frm.doc.dep_emp_name
            );

            const asText = (v) => (v === undefined || v === null) ? '' : String(v).trim();

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

    // -----------------------------------------------------
    // CLEAR FORM AFTER SAVE -> Opens a new blank document
    // -----------------------------------------------------
    after_save(frm) {
        frappe.new_doc('Customer Employee Registration');
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
