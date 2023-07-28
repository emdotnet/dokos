import frappe
from frappe.utils import flt, formatdate, get_datetime_str, get_table_name

from erpnext import get_company_currency, get_default_company
from erpnext.accounts.doctype.fiscal_year.fiscal_year import get_from_and_to_date
from erpnext.setup.utils import get_exchange_rate

__exchange_rates = {}


def get_currency(filters):
	"""
	Returns a dictionary containing currency information. The keys of the dict are
	- company: The company for which we are fetching currency information. if no
	company is specified, it will fallback to the default company.
	- company currency: The functional currency of the said company.
	- presentation currency: The presentation currency to use. Only currencies that
	have been used for transactions will be allowed.
	- report date: The report date.
	:param filters: Report filters
	:type filters: dict

	:return: str - Currency
	"""
	company = get_appropriate_company(filters)
	company_currency = get_company_currency(company)
	presentation_currency = (
		filters["presentation_currency"] if filters.get("presentation_currency") else company_currency
	)

	report_date = filters.get("to_date") or filters.get("period_end_date")

	if not report_date:
		fiscal_year_to_date = get_from_and_to_date(filters.get("to_fiscal_year"))["to_date"]
		report_date = formatdate(get_datetime_str(fiscal_year_to_date), "dd-MM-yyyy")

	currency_map = dict(
		company=company,
		company_currency=company_currency,
		presentation_currency=presentation_currency,
		report_date=report_date,
	)

	return currency_map


def convert(value, from_, to, date):
	"""
	convert `value` from `from_` to `to` on `date`
	:param value: Amount to be converted
	:param from_: Currency of `value`
	:param to: Currency to convert to
	:param date: exchange rate as at this date
	:return: Result of converting `value`
	"""
	rate = get_rate_as_at(date, from_, to)
	converted_value = flt(value) / (rate or 1)
	return converted_value


def get_rate_as_at(date, from_currency, to_currency):
	"""
	Gets exchange rate as at `date` for `from_currency` - `to_currency` exchange rate.
	This calls `get_exchange_rate` so that we can get the correct exchange rate as per
	the user's Accounts Settings.
	It is made efficient by memoising results to `__exchange_rates`
	:param date: exchange rate as at this date
	:param from_currency: Base currency
	:param to_currency: Quote currency
	:return: Retrieved exchange rate
	"""

	rate = __exchange_rates.get("{0}-{1}@{2}".format(from_currency, to_currency, date))
	if not rate:
		rate = get_exchange_rate(from_currency, to_currency, date) or 1
		__exchange_rates["{0}-{1}@{2}".format(from_currency, to_currency, date)] = rate

	return rate


def convert_to_presentation_currency(gl_entries, currency_info):
	"""
	Take a list of GL Entries and change the 'debit' and 'credit' values to currencies
	in `currency_info`.
	:param gl_entries:
	:param currency_info:
	:return:
	"""
	converted_gl_list = []
	presentation_currency = currency_info["presentation_currency"]
	company_currency = currency_info["company_currency"]

	account_currencies = list(set(entry["account_currency"] for entry in gl_entries))

	for entry in gl_entries:
		debit = flt(entry["debit"])
		credit = flt(entry["credit"])
		debit_in_account_currency = flt(entry["debit_in_account_currency"])
		credit_in_account_currency = flt(entry["credit_in_account_currency"])
		account_currency = entry["account_currency"]

		if len(account_currencies) == 1 and account_currency == presentation_currency:
			entry["debit"] = debit_in_account_currency
			entry["credit"] = credit_in_account_currency
		else:
			date = currency_info["report_date"]
			converted_debit_value = convert(debit, presentation_currency, company_currency, date)
			converted_credit_value = convert(credit, presentation_currency, company_currency, date)

			if entry.get("debit"):
				entry["debit"] = converted_debit_value

			if entry.get("credit"):
				entry["credit"] = converted_credit_value

		converted_gl_list.append(entry)

	return converted_gl_list


def get_appropriate_company(filters):
	if filters.get("company"):
		company = filters["company"]
	else:
		company = get_default_company()

	return company


@frappe.whitelist()
def get_invoiced_item_gross_margin(
	sales_invoice=None, item_code=None, company=None, with_item_data=False
):
	from erpnext.accounts.report.gross_profit.gross_profit import GrossProfitGenerator

	sales_invoice = sales_invoice or frappe.form_dict.get("sales_invoice")
	item_code = item_code or frappe.form_dict.get("item_code")
	company = company or frappe.get_cached_value("Sales Invoice", sales_invoice, "company")

	filters = {
		"sales_invoice": sales_invoice,
		"item_code": item_code,
		"company": company,
		"group_by": "Invoice",
	}

	gross_profit_data = GrossProfitGenerator(filters)
	result = gross_profit_data.grouped_data
	if not with_item_data:
		result = sum(d.gross_profit for d in result)

	return result


def get_party_details(party_type, party_list):
	party_details = {}
	party = frappe.qb.DocType(party_type)
	query = frappe.qb.from_(party).select(party.name, party.tax_id).where(party.name.isin(party_list))
	if party_type == "Supplier":
		query = query.select(party.supplier_group)
	else:
		query = query.select(party.customer_group, party.territory)

	party_detail_list = query.run(as_dict=True)
	for party_dict in party_detail_list:
		party_details[party_dict.name] = party_dict
	return party_details


def get_taxes_query(invoice_list, doctype, parenttype):
	taxes = frappe.qb.DocType(doctype)

	query = (
		frappe.qb.from_(taxes)
		.select(taxes.account_head)
		.distinct()
		.where(
			(taxes.parenttype == parenttype)
			& (taxes.docstatus == 1)
			& (taxes.account_head.isnotnull())
			& (taxes.parent.isin([inv.name for inv in invoice_list]))
		)
		.orderby(taxes.account_head)
	)

	if doctype == "Purchase Taxes and Charges":
		return query.where(taxes.category.isin(["Total", "Valuation and Total"]))
	elif doctype == "Sales Taxes and Charges":
		return query.where(taxes.charge_type.isin(["Total", "Valuation and Total"]))
	return query.where(taxes.charge_type.isin(["On Paid Amount", "Actual"]))


def get_journal_entries(filters, args):
	return frappe.db.sql(
		"""
		select je.voucher_type as doctype, je.name, je.posting_date,
		jea.account as {0}, jea.party as {1}, jea.party as {2},
		je.bill_no, je.bill_date, je.remark, je.total_amount as base_net_total,
		je.total_amount as base_grand_total, je.mode_of_payment, jea.project {3}
		from `tabJournal Entry` je left join `tabJournal Entry Account` jea on jea.parent=je.name
		where je.voucher_type='Journal Entry' and jea.party='{4}' {5}
		order by je.posting_date desc, je.name desc""".format(
			args.account,
			args.party,
			args.party_name,
			args.additional_query_columns,
			filters.get(args.party),
			args.conditions,
		),
		filters,
		as_dict=1,
	)


def get_payment_entries(filters, args):
	return frappe.db.sql(
		"""
		select 'Payment Entry' as doctype, name, posting_date, paid_to as {0},
		party as {1}, party_name as {2}, remarks,
		paid_amount as base_net_total, paid_amount_after_tax as base_grand_total,
		mode_of_payment, project, cost_center {3}
		from `tabPayment Entry`
		where party='{4}' {5}
		order by posting_date desc, name desc""".format(
			args.account,
			args.party,
			args.party_name,
			args.additional_query_columns,
			filters.get(args.party),
			args.conditions,
		),
		filters,
		as_dict=1,
	)
