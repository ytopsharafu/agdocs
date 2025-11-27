import frappe

def execute(filters=None):

    columns = [
        {
            "label": "ID",
            "fieldname": "id",
            "fieldtype": "Data",
            "width": 160,
            "html": 1
        },
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Customer Name", "fieldname": "customer", "fieldtype": "Data", "width": 220},
        {"label": "Employee Name", "fieldname": "employee", "fieldtype": "Data", "width": 180},
        {"label": "Dep No", "fieldname": "dep_no", "fieldtype": "Data", "width": 120},
        {"label": "Emp Type", "fieldname": "employee_type", "fieldtype": "Data", "width": 120},
        {"label": "Item", "fieldname": "item", "fieldtype": "Data", "width": 220},
        {"label": "Gov Charge", "fieldname": "gov_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Service Charge", "fieldname": "service_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
    ]

    data = frappe.db.sql("""
        SELECT
            sri.parent AS id,
            sr.date AS date,
            sr.customer AS customer,
            sr.dep_emp_name AS employee,
            sr.department_no AS dep_no,
            sr.employee_type AS employee_type,
            sri.item_code AS item,
            sri.gov_charge AS gov_charge,
            sri.service_charge AS service_charge,
            sri.amount AS amount
        FROM `tabService Request Item` sri
        LEFT JOIN `tabService Request` sr ON sr.name = sri.parent
        ORDER BY sr.date DESC, sri.parent
    """, as_dict=True)

    # REMOVE DUPLICATE HEADER ROWS
    last_id = None
    for row in data:
        if row["id"] == last_id:
            row["id"] = ""
            row["date"] = ""
            row["customer"] = ""
            row["employee"] = ""
            row["dep_no"] = ""
            row["employee_type"] = ""
        else:
            last_id = row["id"]

    # MAKE ID CLICKABLE & BOLD
    for row in data:
        if row["id"]:
            row["id"] = f"<b><a href='/app/service-request/{row['id']}' target='_blank'>{row['id']}</a></b>"

    return columns, data
