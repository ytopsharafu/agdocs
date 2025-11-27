import frappe

def execute(filters=None):

    columns = [
        {"label": "ID", "fieldname": "id", "fieldtype": "Data", "width": 140},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Customer Name", "fieldname": "customer", "fieldtype": "Data", "width": 210},
        {"label": "Employee Name", "fieldname": "employee", "fieldtype": "Data", "width": 200},
        {"label": "Dep No", "fieldname": "dep_no", "fieldtype": "Data", "width": 80},
        {"label": "Emp Type", "fieldname": "employee_type", "fieldtype": "Data", "width": 100},
        {"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "Gov Charge", "fieldname": "gov_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Service Charge", "fieldname": "service_charge", "fieldtype": "Currency", "width": 130},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
    ]

    data = []

    sql = """
    SELECT 
        sri.parent AS id,
        COALESCE(
            NULLIF(sr.status_summary_text, ''),
            CASE
                WHEN sr.docstatus = 0 THEN 'Draft'
                WHEN sr.docstatus = 1 THEN 'Submitted'
                WHEN sr.docstatus = 2 THEN 'Cancelled'
                ELSE ''
            END
        ) AS status,
        sr.date,
        sr.customer,
        sr.dep_emp_name AS employee,
        sr.department_no AS dep_no,
        sr.employee_type AS employee_type,
        sri.item_name,
        sri.gov_charge,
        sri.service_charge,
        sri.amount
    FROM 
        `tabService Request Item` sri
    LEFT JOIN 
        `tabService Request` sr ON sri.parent = sr.name
    ORDER BY 
        sr.date DESC, sr.name DESC, sri.idx
"""

    raw = frappe.db.sql(sql, as_dict=True)

    last_id = None
    for row in raw:
        current_id = row["id"]

        # Make ID clickable + bold
        if current_id:
            row["id"] = f"<b><a href='/app/service-request/{current_id}'>{current_id}</a></b>"

        # Remove duplicate headers for grouped rows  
        if current_id == last_id:
            row["id"] = ""
            row["status"] = ""
            row["date"] = ""
            row["customer"] = ""
            row["employee"] = ""
            row["dep_no"] = ""
            row["employee_type"] = ""
        else:
            last_id = current_id

        data.append(row)

    return columns, data
