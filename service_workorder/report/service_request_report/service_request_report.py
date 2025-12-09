import frappe
from frappe.utils import cint

STATUS_MAP = {"Draft": 0, "Submitted": 1, "Cancelled": 2}

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
    "item_date": "sri.item_date",
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


def parse_multi_select(value):
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


def execute(filters=None):

    filters = frappe._dict(filters or {})

    selected_additional = [
        col for col in parse_multi_select(filters.get("additional_columns"))
        if col in OPTIONAL_COLUMNS
    ]

    limit_value = cint(filters.get("limit_page") or 500)
    if limit_value <= 0:
        limit_value = 500

    page_value = cint(filters.get("page") or 1)
    if page_value <= 0:
        page_value = 1

    offset_value = (page_value - 1) * limit_value

    columns = [
        {
            "label": "ID",
            "fieldname": "id",
            "fieldtype": "Link",
            "options": "Service Request",
            "width": 160,
        },
        {"label": "SR Count", "fieldname": "service_request_count", "fieldtype": "Int", "width": 100, "hidden": 1},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Item Date", "fieldname": "item_date", "fieldtype": "Date", "width": 110},
        {"label": "Customer Name", "fieldname": "customer", "fieldtype": "Data", "width": 220},
        {"label": "Employee Name", "fieldname": "employee", "fieldtype": "Data", "width": 220},
        {"label": "Dep No", "fieldname": "dep_no", "fieldtype": "Data", "width": 120},
        {"label": "Emp Type", "fieldname": "employee_type", "fieldtype": "Data", "width": 120},
        {"label": "Item", "fieldname": "item", "fieldtype": "Data", "width": 220},
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 150,
        },
        {'label': "Created By", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": "Gov Charge", "fieldname": "gov_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Service Charge", "fieldname": "service_charge", "fieldtype": "Currency", "width": 120},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
    ]

    base_fieldnames = {col["fieldname"] for col in columns}
    query_additional = []

    for key in selected_additional:
        if key in base_fieldnames:
            continue
        meta = OPTIONAL_COLUMNS.get(key)
        if not meta:
            continue
        columns.append({
            "label": meta["label"],
            "fieldname": key,
            "fieldtype": meta.get("fieldtype", "Data"),
            "width": meta.get("width", 120),
        })
        query_additional.append(key)

    conditions = []
    values = {}

    date_field = "sri.item_date" if filters.get("date_based_on") == "Item Date" else "sr.date"

    if filters.get("from_date"):
        conditions.append(f"{date_field} >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append(f"{date_field} <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    service_request_id = filters.get("service_request_id") or filters.get("id")
    if service_request_id:
        conditions.append("sri.parent = %(service_request_id)s")
        values["service_request_id"] = service_request_id

    if filters.get("customer"):
        conditions.append("sr.customer = %(customer)s")
        values["customer"] = filters.get("customer")

    if filters.get("employee"):
        conditions.append("sr.dep_emp_name = %(employee)s")
        values["employee"] = filters.get("employee")

    if filters.get("item"):
        conditions.append("sri.item_code = %(item)s")
        values["item"] = filters.get("item")

    if filters.get("item_group"):
        conditions.append("it.item_group = %(item_group)s")
        values["item_group"] = filters.get("item_group")

    if filters.get("owner"):
        conditions.append("sr.owner = %(owner)s")
        values["owner"] = filters.get("owner")

    status_filter = parse_multi_select(filters.get("status"))
    docstatus_values = []
    for status in status_filter:
        mapped = STATUS_MAP.get(status)
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

    base_query = f"""
        FROM `tabService Request Item` sri
        LEFT JOIN `tabService Request` sr ON sr.name = sri.parent
        LEFT JOIN `tabCustomer Employee Registration` ce ON ce.name = sr.dep_emp_name
        LEFT JOIN `tabItem` it ON it.name = sri.item_code
        WHERE {where_clause}
    """

    select_fields = [
        "sri.parent AS id",
        "CASE WHEN sr.docstatus = 0 THEN 'Draft'\n            WHEN sr.docstatus = 1 THEN 'Submitted'\n            WHEN sr.docstatus = 2 THEN 'Cancelled'\n            ELSE '' END AS status",
        "sr.date AS date",
        "sri.item_date AS item_date",
        "sr.customer AS customer",
        "COALESCE(ce.full_name, sr.dep_emp_name) AS employee",
        "sr.department_no AS dep_no",
        "sr.employee_type AS employee_type",
        "sri.item_code AS item",
        "it.item_group AS item_group",
        "sr.owner",
        "sri.gov_charge AS gov_charge",
        "sri.service_charge AS service_charge",
        "sri.amount AS amount",
    ]

    for key in query_additional:
        expression = OPTIONAL_COLUMNS[key]["expression"]
        select_fields.append(f"{expression} AS `{key}`")

    select_clause = ",\n            ".join(select_fields)

    order_field_key = filters.get("sort_by") or ""
    order_direction = "ASC" if (filters.get("sort_order") or "").upper() == "ASC" else "DESC"

    default_order = f"{date_field} DESC, sr.name DESC, sri.idx"
    if order_field_key in SORTABLE_FIELDS:
        primary_sort = SORTABLE_FIELDS[order_field_key]
        order_clause = f"{primary_sort} {order_direction}, sr.name DESC, sri.idx"
    else:
        order_clause = default_order

    data = frappe.db.sql(
        f"""
        SELECT
            {select_clause}
        {base_query}
        ORDER BY {order_clause}
        LIMIT {limit_value} OFFSET {offset_value}
        """,
        values=values,
        as_dict=True,
    )

    last_id = None
    for row in data:
        row["_is_duplicate"] = row["id"] == last_id
        last_id = row["id"]

    totals_sql = f"""
        SELECT
            COUNT(DISTINCT sr.name) AS total_requests,
            COUNT(sri.name) AS total_items,
            COALESCE(SUM(sri.qty), 0) AS total_qty,
            COALESCE(SUM(sri.gov_charge), 0) AS gov_total,
            COALESCE(SUM(sri.service_charge), 0) AS service_total,
            COALESCE(SUM(sri.amount), 0) AS amount_total
        {base_query}
    """

    totals = frappe.db.sql(totals_sql, values=values, as_dict=True)
    total_row = None
    if totals:
        summary_data = totals[0]
        total_requests = summary_data.get("total_requests") or 0
        total_items = summary_data.get("total_items") or 0
        total_row = {
            "is_total_row": 1,
            "id": f"Total ({total_requests})",
            "status": "",
            "date": "",
            "item_date": "",
            "customer": "",
            "employee": "",
            "dep_no": "",
            "employee_type": "",
            "item": "",
            "item_group": f"Items: {total_items}",
            "owner": "",
            "gov_charge": summary_data.get("gov_total") or 0,
            "service_charge": summary_data.get("service_total") or 0,
            "amount": summary_data.get("amount_total") or 0,
        }

        for key in query_additional:
            total_row[key] = ""

        data.append(total_row)

    summary = []
    if totals:
        summary_data = totals[0]
        summary.append({"label": "Total Service Requests", "value": summary_data.get("total_requests") or 0})
        summary.append({"label": "Total Work Detail Rows", "value": summary_data.get("total_items") or 0})
        summary.append({"label": "Total Quantity", "value": summary_data.get("total_qty") or 0})
        summary.append({"label": "Total Gov Charge", "value": summary_data.get("gov_total") or 0})
        summary.append({"label": "Total Service Charge", "value": summary_data.get("service_total") or 0})
        summary.append({"label": "Total Amount", "value": summary_data.get("amount_total") or 0})

    return columns, data, None, summary
