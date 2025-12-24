"""Helper functions that custom Number Cards can use to show bank/credit-card balances."""

from __future__ import annotations

from typing import Iterable, Sequence

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from erpnext.accounts.utils import get_balance_on
from erpnext.accounts.report.bank_reconciliation_statement.bank_reconciliation_statement import (
	get_entries as get_reco_entries,
)


def _normalize_filters(filters: Iterable | dict | str | None) -> frappe._dict:
	"""Convert assorted filter payloads into a frappe._dict."""

	if not filters:
		return frappe._dict({"filters": []})

	if isinstance(filters, str):
		try:
			filters = frappe.parse_json(filters)
		except Exception:
			return frappe._dict()

	if isinstance(filters, dict):
		return frappe._dict(filters)

	data: dict[str, object] = {}
	for row in filters or []:
		if not isinstance(row, (list, tuple)) or len(row) < 4:
			continue
		_, fieldname, operator, value = row[:4]
		if operator == "=":
			data[fieldname] = value

	return frappe._dict(data)


def _ensure_list(value: object | None) -> list:
	if value is None:
		return []
	if isinstance(value, (list, tuple, set)):
		return list(value)
	return [value]


def _pick_company(filters: frappe._dict) -> str | None:
	company = (
		filters.get("company")
		or frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or frappe.db.get_default("company")
	)
	return company


def _pick_currency(company: str | None) -> str | None:
	if not company:
		return frappe.defaults.get_global_default("currency")
	return frappe.get_cached_value("Company", company, "default_currency")


def _fetch_accounts(
	account_names: Sequence[str] | None,
	company: str | None,
	credit_card_flag: int | None,
) -> list[frappe._dict]:
	filters: dict[str, object] = {"disabled": 0, "is_company_account": 1}
	if account_names:
		if len(account_names) == 1:
			filters["name"] = account_names[0]
		else:
			filters["name"] = ["in", account_names]

	if company:
		filters["company"] = company

	has_credit_flag = frappe.db.has_column("Bank Account", "is_credit_card")
	if credit_card_flag is not None and has_credit_flag:
		filters["is_credit_card"] = credit_card_flag

	fields = ["name", "account", "company"]
	if has_credit_flag:
		fields.append("is_credit_card")

	return frappe.get_all("Bank Account", filters=filters, fields=fields, as_list=False)


def _aggregate_gl_balance(accounts: list[frappe._dict], balance_date: str, fallback_company: str | None) -> tuple[float, str | None]:
	total = 0.0
	currency: str | None = None

	for account in accounts:
		account_name = account.get("account")
		if not account_name:
			continue

		company = account.get("company") or fallback_company
		total += flt(
			get_balance_on(
				account=account_name,
				date=balance_date,
				company=company,
				in_account_currency=False,
			)
		)

		if not currency and company:
			currency = _pick_currency(company)

	return total, currency or _pick_currency(fallback_company)


@frappe.whitelist()
@frappe.read_only()
def get_bank_account_current_balance(filters=None, as_on: str | None = None):
	"""Return the ledger balance for the requested Bank Account(s).

	`filters` can contain:
	- `bank_account` / `name`: a single account name or list of names
	- `company`: limits the search to the specified company
	- `is_credit_card`: 0/1 to include only bank or credit-card accounts
	- `as_on` / `date` / `posting_date`: balance cutoff date (defaults to today)
	"""

	parsed_filters = _normalize_filters(filters)
	company = _pick_company(parsed_filters)

	account_names = _ensure_list(parsed_filters.get("bank_account") or parsed_filters.get("name"))

	credit_flag = parsed_filters.get("is_credit_card")
	if credit_flag is not None:
		credit_flag = cint(credit_flag)

	target_date = (
		as_on
		or parsed_filters.get("as_on")
		or parsed_filters.get("date")
		or parsed_filters.get("posting_date")
		or nowdate()
	)

	accounts = _fetch_accounts(account_names, company, credit_flag)
	if not accounts:
		if account_names:
			frappe.throw(_("No Bank Account found for the provided filters."))
		return {"value": 0, "fieldtype": "Currency", "options": _pick_currency(company)}

	total, currency = _aggregate_gl_balance(accounts, target_date, company)

	return {"value": total, "fieldtype": "Currency", "options": currency}


def _get_bank_account_doc(filters: frappe._dict) -> frappe._dict:
	bank_account_name = filters.get("bank_account") or filters.get("name")
	if not bank_account_name:
		frappe.throw(_("Please set a Bank Account filter."))

	doc = frappe.get_doc("Bank Account", bank_account_name)
	if not doc.account:
		frappe.throw(_("Bank Account {0} is missing the linked GL Account.").format(doc.name))
	return doc


@frappe.whitelist()
@frappe.read_only()
def get_outstanding_bank_balance(filters=None, as_on: str | None = None):
	"""Return the outstanding balance (Closing = Opening + Total) from the bank reconciliation statement."""

	parsed_filters = _normalize_filters(filters)
	bank_account = _get_bank_account_doc(parsed_filters)

	report_date = (
		as_on
		or parsed_filters.get("as_on")
		or parsed_filters.get("date")
		or parsed_filters.get("posting_date")
		or nowdate()
	)

	report_filters = frappe._dict(
		{
			"account": bank_account.account,
			"company": parsed_filters.get("company") or bank_account.company,
			"report_date": report_date,
			"include_pos_transactions": 1,
		}
	)

	entries = get_reco_entries(report_filters)

	total_debit = sum(flt((row or {}).get("debit") or 0) for row in entries)
	total_credit = sum(flt((row or {}).get("credit") or 0) for row in entries)

	outstanding = total_debit - total_credit

	account_currency = frappe.db.get_value("Account", bank_account.account, "account_currency")

	return {
		"value": outstanding,
		"fieldtype": "Currency",
		"options": account_currency or _pick_currency(bank_account.company),
	}
