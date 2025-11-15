frappe.ui.form.on('Service Form Order', {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 1) {
            frm.add_custom_button('Create Sales Order', () => {
                frappe.call({
                    method: 'service_workorder.api.create_sales_order_from_service_form',
                    args: { service_form_order: frm.doc.name },
                    callback: function(r) {
                        if (r.message) frappe.set_route('Form', 'Sales Order', r.message);
                    }
                });
            });

            frm.add_custom_button('Create Sales Invoice', () => {
                frappe.call({
                    method: 'service_workorder.api.create_sales_invoice_from_service_form',
                    args: { service_form_order: frm.doc.name },
                    callback: function(r) {
                        if (r.message) frappe.set_route('Form', 'Sales Invoice', r.message);
                    }
                });
            });
        }

        // Auto-calc total
        if (frm.doc.items && frm.doc.items.length > 0) {
            let total = 0;
            frm.doc.items.forEach(i => {
                i.amount = flt(i.qty) * flt(i.rate);
                total += i.amount;
            });
            frm.set_value('total', total);
            frm.refresh_field('items');
        }
    }
});

frappe.ui.form.on('Service Form Order Item', {
    qty: update_amount,
    rate: update_amount
});

function update_amount(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    row.amount = flt(row.qty) * flt(row.rate);
    frm.refresh_field('items');
    let total = 0;
    (frm.doc.items || []).forEach(i => total += flt(i.amount));
    frm.set_value('total', total);
}
