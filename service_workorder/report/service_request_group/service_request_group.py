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

SORTABLE_FIELDS = {
    "date": "sr.date",
    "customer": "sr.customer",
    "employee": "ce.full_name",
    "dep_no": "sr.department_no",
    "employee_type": "sr.employee_type",
    "item": "sri.item_code",
    "item_group": "it.item_group",
    "owner": "sr.owner",
    "gov_charge": "sri.gov_charge",
    "service_charge": "sri.service_charge",
    "amount": "sri.amount",
}

def execute(filters=None):

    # -------------------------
    # Filter Definitions Handler
    # -------------------------

    filters = frappe._dict(filters or {})

    conditions = []
    values = {}

    def parse_multi_select_values(value):
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, str):
            try:
                parsed = frappe.parse_json(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value]

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

    # Limit & pagination
    limit_value = cint(filters.get("limit_page") or 500)
    if limit_value <= 0:
        limit_value = 500

    page_value = cint(filters.get("page") or 1)
    if page_value <= 0:
        page_value = 1

    offset_value = (page_value - 1) * limit_value

    selected_additional = [
        col for col in parse_multi_select_values(filters.get("additional_columns"))
        if col in OPTIONAL_COLUMNS
    ]

    status_filter = parse_multi_select_values(filters.get("status"))
    if status_filter:
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        docstatus_values = []
        for status in status_filter:
            mapped = status_map.get(status)
            if mapped is None:
                try:
                    mapped = cint(status)
                except Exception:
                    continue
            docstatus_values.append(mapped)

        if docstatus_values:
            conditions.append("sr.docstatus IN %(docstatus_values)s")
            values["docstatus_values"] = tuple(docstatus_values)

    where_clause = " AND ".join(["1=1"] + conditions)

    # -------------------------
    # Column Definitions
    # -------------------------
    columns = [
        {
            "label": "ID",
            "fieldname": "id",
            "fieldtype": "Link",
            "options": "Service Request",
            "width": 200,
        },
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Item Date", "fieldname": "item_date", "fieldtype": "Date", "width": 110},
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

    base_fieldnames = {col["fieldname"] for col in columns}
    query_additional = []

    for key in selected_additional:
        if key in base_fieldnames:
            continue
        col = OPTIONAL_COLUMNS.get(key)
        if not col:
            continue
        columns.append({
            "label": col["label"],
            "fieldname": key,
            "fieldtype": col.get("fieldtype", "Data"),
            "width": col.get("width", 120),
        })
        query_additional.append(key)

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
        "sri.item_date AS item_date",
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

    for key in query_additional:
        expression = OPTIONAL_COLUMNS[key]["expression"]
        select_fields.append(f"{expression} AS `{key}`")

    select_clause = ",\n        ".join(select_fields)

    order_field_key = filters.get("sort_by")
    order_direction = "ASC" if (filters.get("sort_order") or "").upper() == "ASC" else "DESC"

    default_order = "sr.date DESC, sr.name DESC, sri.idx"
    if order_field_key in SORTABLE_FIELDS:
        primary_sort = SORTABLE_FIELDS[order_field_key]
        order_clause = f"{primary_sort} {order_direction}, sr.name DESC, sri.idx"
    else:
        order_clause = default_order

    sql = f"""
    SELECT 
        {select_clause}

    {base_query}

    ORDER BY 
        {order_clause}

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
        row["_is_duplicate"] = current_id == last_id
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
            "item_date": "",
            "owner": "",
            "gov_charge": totals_data.get("gov_total") or 0,
            "service_charge": totals_data.get("service_total") or 0,
            "amount": totals_data.get("amount_total") or 0,
            "is_total_row": 1,
        }

        for key in selected_additional:
            total_row[key] = ""

        total_row["_is_duplicate"] = 0
        data.append(total_row)

    return columns, data
