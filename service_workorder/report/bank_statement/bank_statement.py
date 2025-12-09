import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from erpnext.accounts.report.bank_reconciliation_statement import (
	bank_reconciliation_statement as bank_reco_report,
)
from erpnext.accounts.utils import get_balance_on

DOCSTATUS_MAP = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
_GL_ENTRY_COLUMNS = set()
CLEARANCE_SOURCES = {
	"Payment Entry": ("Payment Entry", "clearance_date"),
	"Journal Entry": ("Journal Entry", "clearance_date"),
	"Purchase Invoice": ("Purchase Invoice", "clearance_date"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})

	filters.docstatus = get_docstatus_value(filters.get("docstatus"))

	if not filters.get("company") and filters.get("account"):
		filters.company = frappe.db.get_value("Account", filters.account, "company")

	show_bt_id = cint(filters.get("show_bt_id"))
	ensure_optional_columns(show_bt_id)
	include_opening = cint(filters.get("include_opening"))
	include_future = cint(filters.get("include_future_entries"))

	columns = get_columns(show_bt_id)

	if not all([filters.get("account"), filters.get("from_date"), filters.get("to_date")]):
		return columns, []

	# -----------------------------
	# OPENING BALANCE
	# -----------------------------
	opening_balance = get_opening_balance(filters)
	data = []

	if include_opening:
		data.append({
			"posting_date": filters.from_date,
			"voucher_type": "",
			"voucher_no": "",
			"party_type": "",
			"party": "",
			"against_account": "",
			"remark": "Opening Balance",
			"cheque_no": "",
			"mode_of_payment": "",
			"debit": "",
			"credit": "",
			"running_balance": opening_balance,
			"reconciled_status": "",
		})

	# -----------------------------
	# FETCH GL ENTRIES
	# -----------------------------
	ledger_entries = fetch_gl_entries(filters, show_bt_id)
	future_entries = fetch_gl_entries(filters, show_bt_id, mode="future") if include_future else []
	clearance_map = get_clearance_date_map(ledger_entries + future_entries)

	# -----------------------------
	# RUNNING BALANCE + ROWS
	# -----------------------------
	running = opening_balance

	for d in ledger_entries:
		running += d.debit - d.credit
		clearance_date = clearance_map.get((d.voucher_type, d.voucher_no))

		row = {
			"posting_date": d.posting_date,
			"voucher_type": d.voucher_type,
			"voucher_no": d.voucher_no,
			"party_type": d.party_type or "",
			"party": d.party or "",
			"against_account": d.against or "",
			"remark": d.remarks or "",
			"cheque_no": d.get("cheque_no") or "",
			"mode_of_payment": d.get("mode_of_payment") or "",
			"debit": d.debit,
			"credit": d.credit,
			"running_balance": running,
			"reconciled_status": get_reconciled_status(clearance_date, d.posting_date, filters.to_date),
		}

		if show_bt_id:
			row["bank_transaction_id"] = d.get("bank_transaction_id") or ""

		data.append(row)

	# -----------------------------
	# CLOSING BALANCE + SUMMARY
	# -----------------------------
	ledger_balance = get_balance_on(filters.account, filters.to_date) if filters.get("to_date") else running
	if ledger_balance is None:
		ledger_balance = running

	data.append({
		"posting_date": filters.to_date,
		"voucher_type": "",
		"voucher_no": "",
		"party_type": "",
		"party": "",
		"against_account": "",
		"remark": "Closing Balance",
		"cheque_no": "",
		"mode_of_payment": "",
		"debit": "",
		"credit": "",
		"running_balance": ledger_balance,
		"reconciled_status": "",
	})

	if future_entries:
		data.append({})
		data.append({"remark": _("Future-dated entries after {0}").format(filters.to_date)})
		future_running = ledger_balance
		for d in future_entries:
			future_running += d.debit - d.credit
			clearance_date = clearance_map.get((d.voucher_type, d.voucher_no))
			row = {
				"posting_date": d.posting_date,
				"voucher_type": d.voucher_type,
				"voucher_no": d.voucher_no,
				"party_type": d.party_type or "",
				"party": d.party or "",
				"against_account": d.against or "",
				"remark": d.remarks or "",
				"cheque_no": d.get("cheque_no") or "",
				"mode_of_payment": d.get("mode_of_payment") or "",
				"debit": d.debit,
				"credit": d.credit,
				"running_balance": future_running,
				"reconciled_status": get_reconciled_status(clearance_date, d.posting_date, filters.to_date),
			}
			if show_bt_id:
				row["bank_transaction_id"] = d.get("bank_transaction_id") or ""
			data.append(row)

	data.extend(get_summary_rows(filters, ledger_balance))

	return columns, data


def get_columns(show_bt_id):
	columns = [
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": "Voucher Type", "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{
			"label": "Voucher No",
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 130},
		{"label": "Party", "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": "Against Account", "fieldname": "against_account", "fieldtype": "Data", "width": 210},
		{"label": "Remark", "fieldname": "remark", "fieldtype": "Data", "width": 220},
		{"label": "Cheque No", "fieldname": "cheque_no", "fieldtype": "Data", "width": 110},
		{"label": "Mode of Payment", "fieldname": "mode_of_payment", "fieldtype": "Data", "width": 130},
		{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 110},
		{"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 110},
		{"label": "Balance", "fieldname": "running_balance", "fieldtype": "Currency", "width": 150},
		{"label": "Reconciled Status", "fieldname": "reconciled_status", "fieldtype": "Data", "width": 140},
	]

	if show_bt_id:
		columns.append({"label": "Bank Txn ID", "fieldname": "bank_transaction_id", "fieldtype": "Data", "width": 150})
	return columns


# Helper: Opening Balance
def get_opening_balance(filters):
	conditions = build_conditions(filters, mode="opening")
	opening = frappe.db.sql(f"""
		SELECT SUM(debit - credit) 
		FROM `tabGL Entry`
		WHERE {conditions}
	""", filters)

	return (opening[0][0] or 0) if opening else 0


def get_gl_entry_select_fields(show_bt_id):
	fields = [
		"posting_date",
		"voucher_type",
		"voucher_no",
		"party_type",
		"party",
		"debit",
		"credit",
		"against",
		"remarks",
	]

	if gl_entry_has_column("cheque_no"):
		fields.append("cheque_no")

	if gl_entry_has_column("mode_of_payment"):
		fields.append("mode_of_payment")

	if show_bt_id and gl_entry_has_column("bank_transaction_id"):
		fields.append("bank_transaction_id")

	return fields


def fetch_gl_entries(filters, show_bt_id, mode="range"):
	conditions = build_conditions(filters, mode=mode)
	select_fields = get_gl_entry_select_fields(show_bt_id)
	return frappe.db.sql(
		f"""
		SELECT {", ".join(select_fields)}
		FROM `tabGL Entry`
		WHERE {conditions}
		ORDER BY posting_date, creation, name
	""",
		filters,
		as_dict=True,
	)


def build_conditions(filters, mode="range"):
	conditions = ["account=%(account)s", "docstatus=%(docstatus)s"]

	if mode == "opening":
		conditions.append("posting_date < %(from_date)s")
	elif mode == "future":
		conditions.append("posting_date > %(to_date)s")
	else:
		conditions.append("posting_date BETWEEN %(from_date)s AND %(to_date)s")

	if filters.get("company"):
		conditions.append("company=%(company)s")

	if filters.get("party_type"):
		conditions.append("party_type=%(party_type)s")

	if filters.get("party"):
		conditions.append("party=%(party)s")

	if filters.get("mode_of_payment"):
		if not gl_entry_has_column("mode_of_payment"):
			frappe.throw(_("Mode of Payment filter is not available for this site."))
		conditions.append("mode_of_payment=%(mode_of_payment)s")

	if filters.get("voucher_type"):
		conditions.append("voucher_type=%(voucher_type)s")

	if cint(filters.get("docstatus")) == 1 and gl_entry_has_column("is_cancelled"):
		conditions.append("ifnull(is_cancelled, 0) = 0")

	return " AND ".join(conditions)


def get_docstatus_value(value):
	if value in (0, 1, 2):
		return value

	if isinstance(value, str):
		stripped = value.strip()
		if stripped.isdigit():
			return cint(stripped)

		return DOCSTATUS_MAP.get(stripped, 1)

	if value is None or value == "":
		return 1

	return cint(value)


def gl_entry_has_column(column_name):
	if not _GL_ENTRY_COLUMNS:
		_GL_ENTRY_COLUMNS.update(frappe.db.get_table_columns("GL Entry"))
	return column_name in _GL_ENTRY_COLUMNS


def ensure_optional_columns(show_bt_id):
	if show_bt_id and not gl_entry_has_column("bank_transaction_id"):
		frappe.throw(_("Bank Transaction ID column is not available in GL Entry on this site."))


def get_clearance_date_map(entries):
	clearance_map = {}
	if not entries:
		return clearance_map

	requests = {}
	for entry in entries:
		source = CLEARANCE_SOURCES.get(entry.voucher_type)
		if source and entry.voucher_no:
			requests.setdefault(source[0], set()).add(entry.voucher_no)

	for doctype, names in requests.items():
		if not names:
			continue
		rows = frappe.db.get_all(doctype, filters={"name": ("in", list(names))}, fields=["name", "clearance_date"])
		for row in rows:
			clearance_map[(doctype, row.name)] = row.clearance_date

	return clearance_map


def get_reconciled_status(clearance_date, posting_date, report_date):
	if not report_date:
		return ""

	report = getdate(report_date)
	posting = getdate(posting_date) if posting_date else None

	if clearance_date:
		clearance = getdate(clearance_date)
		return _("Reconciled") if clearance <= report else _("Pending Clearance")

	if posting and posting > report:
		return _("Future Dated")

	return _("Unreconciled")


def get_summary_rows(filters, ledger_balance):
	if not (filters.get("account") and filters.get("company") and filters.get("to_date")):
		return []

	brs_filters = frappe._dict(
		{
			"account": filters.account,
			"company": filters.company,
			"report_date": filters.to_date,
			"include_pos_transactions": cint(filters.get("include_pos_transactions")),
		}
	)

	outstanding_entries = bank_reco_report.get_entries_for_bank_reconciliation_statement(brs_filters) or []
	outstanding_debit = sum(flt(row.get("debit")) for row in outstanding_entries)
	outstanding_credit = sum(flt(row.get("credit")) for row in outstanding_entries)

	incorrect_amount = (
		bank_reco_report.get_amounts_not_reflected_in_system_for_bank_reconciliation_statement(brs_filters) or 0.0
	)

	ledger_balance = flt(ledger_balance)
	calculated_balance = ledger_balance - outstanding_debit + outstanding_credit + incorrect_amount

	return [
		{
			"remark": _("Bank Statement balance as per General Ledger (till {0})").format(filters.to_date),
			"running_balance": ledger_balance,
		},
		{},
		{
			"remark": _("Outstanding Cheques and Deposits to clear"),
			"debit": outstanding_debit,
			"credit": outstanding_credit,
		},
		{
			"remark": _("Cheques and Deposits incorrectly cleared"),
			"running_balance": incorrect_amount,
		},
		{},
		{
			"remark": _("Calculated Bank Statement balance"),
			"running_balance": calculated_balance,
		},
	]
