import frappe
from frappe.utils import cint

OPTIONAL_COLUMNS = {
    "payment_type": {
        "label": "Payment Type",
        "fieldtype": "Data",
        "width": 150,
        "expression": "sri.payment_type",
    },
    "item_status": {
        "label": "Item Status",
        "fieldtype": "Data",
        "width": 120,
        "expression": "sri.status",
    },
    "item_date": {
        "label": "Item Date",
        "fieldtype": "Date",
        "width": 110,
        "expression": "sri.item_date",
    },
    "company": {
        "label": "Company",
        "fieldtype": "Data",
        "width": 200,
        "expression": "sr.company",
    },
    "tax_category": {
        "label": "Tax Category",
        "fieldtype": "Data",
        "width": 150,
        "expression": "sr.tax_category",
    },
    "sales_taxes_and_charges_template": {
        "label": "Tax Template",
        "fieldtype": "Data",
        "width": 180,
        "expression": "sr.sales_taxes_and_charges_template",
    },
}

def execute(filters=None):

    # -------------------------
    # Filter Definitions Handler
    # -------------------------

    filters = frappe._dict(filters or {})

    conditions = []
    values = {}

    # Date Range Filters
    if filters.get("from_date"):
        conditions.append("sr.date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("sr.date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("service_request_id"):
        conditions.append("sri.parent = %(service_request_id)s")
        values["service_request_id"] = filters.service_request_id

    # Customer Filter
    if filters.get("customer"):
        conditions.append("sr.customer = %(customer)s")
        values["customer"] = filters.customer

    # Employee Filter
    if filters.get("employee"):
        conditions.append("sr.dep_emp_name = %(employee)s")
        values["employee"] = filters.employee

    # Item Filter
    if filters.get("item"):
        conditions.append("sri.item_code = %(item)s")
        values["item"] = filters.item

    # Item Group Filter
    if filters.get("item_group"):
        conditions.append("it.item_group = %(item_group)s")
        values["item_group"] = filters.item_group

    if filters.get("owner"):
        conditions.append("sr.owner = %(owner)s")
        values["owner"] = filters.owner

    where_clause = " AND ".join(["1=1"] + conditions)

    # Limit & pagination
    limit_value = cint(filters.get("limit_page") or 500)
    if limit_value <= 0:
        limit_value = 500

    page_value = cint(filters.get("page") or 1)
    if page_value <= 0:
        page_value = 1

    offset_value = (page_value - 1) * limit_value

    def parse_additional_columns(value):
        if not value:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = frappe.parse_json(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value]

    selected_additional = [
        col for col in parse_additional_columns(filters.get("additional_columns"))
        if col in OPTIONAL_COLUMNS
    ]

    # -------------------------
    # Column Definitions
    # -------------------------
    columns = [
        {"label": "ID", "fieldname": "id", "fieldtype": "Data", "width": 200},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {
            "label": "Customer Name",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 310,
        },
        {"label": "Employee Name", "fieldname": "full_name", "fieldtype": "Data", "width": 310},
        {"label": "Dep No", "fieldname": "dep_no", "fieldtype": "Data", "width": 80},
        {"label": "Emp Type", "fieldname": "employee_type", "fieldtype": "Data", "width": 100},
        {
            "label": "Item",
            "fieldname": "item_name",
            "fieldtype": "Link",
            "options": "Item",
            "width": 280,
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 150,
        },
        {
            "label": "Created By",
            "fieldname": "owner",
            "fieldtype": "Link",
            "options": "User",
            "width": 180,
        },
        {"label": "Gov Charge", "fieldname": "gov_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Service Charge", "fieldname": "service_charge", "fieldtype": "Currency", "width": 130},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
    ]

    for key in selected_additional:
        col = OPTIONAL_COLUMNS.get(key)
        if not col:
            continue
        columns.append({
            "label": col["label"],
            "fieldname": key,
            "fieldtype": col.get("fieldtype", "Data"),
            "width": col.get("width", 120),
        })

    base_query = f"""
    FROM 
        `tabService Request Item` sri
    LEFT JOIN 
        `tabService Request` sr ON sri.parent = sr.name
    LEFT JOIN
        `tabCustomer Employee Registration` ce ON ce.name = sr.dep_emp_name
    LEFT JOIN
        `tabItem` it ON it.name = sri.item_code

    WHERE {where_clause}
    """

    # -------------------------
    # SQL Query
    # -------------------------
    select_fields = [
        "sri.parent AS id",
        "CASE WHEN sr.docstatus = 0 THEN 'Draft'\n            WHEN sr.docstatus = 1 THEN 'Submitted'\n            WHEN sr.docstatus = 2 THEN 'Cancelled'\n            ELSE '' END AS status",
        "sr.date",
        "sr.customer",
        "ce.full_name AS full_name",
        "sr.department_no AS dep_no",
        "sr.employee_type AS employee_type",
        "sri.item_code AS item_name",
        "it.item_group AS item_group",
        "sr.owner",
        "sri.gov_charge",
        "sri.service_charge",
        "sri.amount",
    ]

    for key in selected_additional:
        expression = OPTIONAL_COLUMNS[key]["expression"]
        select_fields.append(f"{expression} AS `{key}`")

    select_clause = ",\n        ".join(select_fields)

    sql = f"""
    SELECT 
        {select_clause}

    {base_query}

    ORDER BY 
        sr.date DESC, sr.name DESC, sri.idx

    LIMIT {limit_value} OFFSET {offset_value}
    """

    raw = frappe.db.sql(sql, values=values, as_dict=True)
    data = []

    # -------------------------
    # Row grouping by parent ID
    # -------------------------
    last_id = None

    for row in raw:
        current_id = row["id"]

        # Convert ID to clickable link
        if current_id:
            row["id"] = f"<b><a href='/app/service-request/{current_id}'>{current_id}</a></b>"

        # Hide repeated parent information for grouped rows
        if current_id == last_id:
            row["id"] = ""
            row["status"] = ""
            row["date"] = ""
            row["customer"] = ""
            row["full_name"] = ""
            row["dep_no"] = ""
            row["employee_type"] = ""
        else:
            last_id = current_id

        data.append(row)

    totals_sql = f"""
    SELECT
        COALESCE(SUM(sri.gov_charge), 0) AS gov_total,
        COALESCE(SUM(sri.service_charge), 0) AS service_total,
        COALESCE(SUM(sri.amount), 0) AS amount_total
    {base_query}
    """

    totals = frappe.db.sql(totals_sql, values=values, as_dict=True)
    totals_data = totals[0] if totals else {}

    if totals_data:
        total_row = {
            "id": "Total",
            "status": "",
            "date": "",
            "customer": "",
            "full_name": "",
            "dep_no": "",
            "employee_type": "",
            "item_name": "",
            "item_group": "",
            "owner": "",
            "gov_charge": totals_data.get("gov_total") or 0,
            "service_charge": totals_data.get("service_total") or 0,
            "amount": totals_data.get("amount_total") or 0,
            "is_total_row": 1,
        }

        for key in selected_additional:
            total_row[key] = ""

        data.append(total_row)

    return columns, data
