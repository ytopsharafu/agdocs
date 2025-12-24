import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["cer.docstatus < 2"]
	params = {}

	if filters.get("customer"):
		conditions.append("cer.customer_name = %(customer)s")
		params["customer"] = filters.customer

	if filters.get("employee_type"):
		conditions.append("cer.employee_type = %(employee_type)s")
		params["employee_type"] = filters.employee_type

	need_uid = bool(int(filters.get("require_uid") or 0))
	need_dep = bool(int(filters.get("require_department") or 0))

	missing_clauses = []

	if need_uid:
		missing_clauses.append("(coalesce(cer.uid_no, '') = '')")
	if need_dep:
		missing_clauses.append("(coalesce(cer.dep_no1, '') = '' and coalesce(cer.dep_no2, '') = '')")

	if not missing_clauses:
		missing_clauses.append(
			"(coalesce(cer.uid_no, '') = '' or (coalesce(cer.dep_no1, '') = '' and coalesce(cer.dep_no2, '') = ''))"
		)

	conditions.append("(" + " or ".join(missing_clauses) + ")")

	data = frappe.db.sql(
		"""
		select
			name,
			customer_name,
			employee_type,
			full_name,
			uid_no,
			dep_no1,
			dep_no2,
			new_employee
		from `tabCustomer Employee Registration` cer
		where {conditions}
		order by customer_name, full_name
		""".format(conditions=" and ".join(conditions)),
		params,
		as_dict=True,
	)

	columns = [
		{"label": _("Employee"), "fieldname": "name", "fieldtype": "Link", "options": "Customer Employee Registration", "width": 160},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Employee Type"), "fieldname": "employee_type", "fieldtype": "Data", "width": 110},
		{"label": _("Full Name"), "fieldname": "full_name", "fieldtype": "Data", "width": 200},
		{"label": _("UID No"), "fieldname": "uid_no", "fieldtype": "Data", "width": 130},
		{"label": _("Dept No 1"), "fieldname": "dep_no1", "fieldtype": "Data", "width": 100},
		{"label": _("Dept No 2"), "fieldname": "dep_no2", "fieldtype": "Data", "width": 100},
		{"label": _("New Employee"), "fieldname": "new_employee", "fieldtype": "Check", "width": 100},
	]

	return columns, data
