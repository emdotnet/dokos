# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _, msgprint
from frappe.utils import flt

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
from erpnext.accounts.report.utils import (
	get_journal_entries,
	get_party_details,
	get_payment_entries,
	get_taxes_query,
)


def execute(filters=None):
	return _execute(filters)


def _execute(filters=None, additional_table_columns=None):
	if not filters:
		filters = {}

	include_payments = filters.get("include_payments")
	invoice_list = get_invoices(filters, additional_query_columns)
	if filters.get("include_payments"):
		invoice_list += get_payments(filters, additional_query_columns)
	columns, expense_accounts, tax_accounts, unrealized_profit_loss_accounts = get_columns(
		invoice_list, additional_table_columns, include_payments
	)

	if not invoice_list:
		msgprint(_("No record found"))
		return columns, invoice_list

	invoice_expense_map = get_invoice_expense_map(invoice_list)
	internal_invoice_map = get_internal_invoice_map(invoice_list)
	invoice_expense_map, invoice_tax_map = get_invoice_tax_map(
		invoice_list, invoice_expense_map, expense_accounts, include_payments
	)
	invoice_po_pr_map = get_invoice_po_pr_map(invoice_list)
	suppliers = list(set(d.supplier for d in invoice_list))
	supplier_details = get_party_details("Supplier", suppliers)

	company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")

	data = []
	for inv in invoice_list:
		# invoice details
		purchase_order = list(set(invoice_po_pr_map.get(inv.name, {}).get("purchase_order", [])))
		purchase_receipt = list(set(invoice_po_pr_map.get(inv.name, {}).get("purchase_receipt", [])))
		project = list(set(invoice_po_pr_map.get(inv.name, {}).get("project", [])))

		row = [inv.doctype, inv.name, inv.posting_date, inv.supplier, inv.supplier_name]

		if additional_query_columns:
			for col in additional_query_columns:
				row.append(inv.get(col))

		row += [
			supplier_details.get(inv.supplier).get("supplier_group"),  # supplier_group
			supplier_details.get(inv.supplier).get("tax_id"),
			inv.credit_to,
			inv.mode_of_payment,
			", ".join(project) if inv.doctype == "Purchase Invoice" else inv.project,
			inv.bill_no,
			inv.bill_date,
			inv.remarks,
			", ".join(purchase_order),
			", ".join(purchase_receipt),
			company_currency,
		]

		# map expense values
		base_net_total = 0
		for expense_acc in expense_accounts:
			if inv.is_internal_supplier and inv.company == inv.represents_company:
				expense_amount = 0
			else:
				expense_amount = flt(invoice_expense_map.get(inv.name, {}).get(expense_acc))
			base_net_total += expense_amount
			row.append(expense_amount)

		# Add amount in unrealized account
		for account in unrealized_profit_loss_accounts:
			row.append(flt(internal_invoice_map.get((inv.name, account))))

		# net total
		row.append(base_net_total or inv.base_net_total)

		# tax account
		total_tax = 0
		for tax_acc in tax_accounts:
			if tax_acc not in expense_accounts:
				tax_amount = flt(invoice_tax_map.get(inv.name, {}).get(tax_acc))
				total_tax += tax_amount
				row.append(tax_amount)

		# total tax, grand total, rounded total & outstanding amount
		row += [total_tax, inv.base_grand_total, flt(inv.base_grand_total, 0), inv.outstanding_amount]
		data.append(row)

	return columns, sorted(data, key=lambda x: x[2])


def get_columns(invoice_list, additional_table_columns, include_payments=False):
	"""return columns based on filters"""
	columns = [
		_("Voucher Type") + ":Data:120",
		_("Voucher No") + ":Dynamic Link/voucher_type:120",
		_("Posting Date") + ":Date:80",
		_("Supplier Id") + "::120",
		_("Supplier Name") + "::120",
	]

	if additional_table_columns:
		columns += additional_table_columns

	columns += [
		_("Supplier Group") + ":Link/Supplier Group:120",
		_("Tax Id") + "::50",
		_("Payable Account") + ":Link/Account:120",
		_("Mode of Payment") + ":Link/Mode of Payment:80",
		_("Project") + ":Link/Project:80",
		_("Bill No") + "::120",
		_("Bill Date") + ":Date:80",
		_("Remarks") + "::150",
		_("Purchase Order") + ":Link/Purchase Order:100",
		_("Purchase Receipt") + ":Link/Purchase Receipt:100",
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "width": 80},
	]
	expense_accounts = []
	tax_accounts = []
	unrealized_profit_loss_accounts = []

	if invoice_list:
		expense_accounts = frappe.db.sql_list(
			"""select distinct expense_account
			from `tabPurchase Invoice Item` where docstatus = 1
			and (expense_account is not null and expense_account != '')
			and parent in (%s) order by expense_account"""
			% ", ".join(["%s"] * len(invoice_list)),
			tuple(inv.name for inv in invoice_list),
		)

		purchase_taxes_query = get_taxes_query(
			invoice_list, "Purchase Taxes and Charges", "Purchase Invoice"
		)
		purchase_tax_accounts = purchase_taxes_query.run(as_dict=True, pluck="account_head")
		tax_accounts = purchase_tax_accounts

		if include_payments:
			advance_taxes_query = get_taxes_query(
				invoice_list, "Advance Taxes and Charges", "Payment Entry"
			)
			advance_tax_accounts = advance_taxes_query.run(as_dict=True, pluck="account_head")
			tax_accounts = set(tax_accounts + advance_tax_accounts)

		unrealized_profit_loss_accounts = frappe.db.sql_list(
			"""SELECT distinct unrealized_profit_loss_account
			from `tabPurchase Invoice` where docstatus = 1 and name in (%s)
			and ifnull(unrealized_profit_loss_account, '') != ''
			order by unrealized_profit_loss_account"""
			% ", ".join(["%s"] * len(invoice_list)),
			tuple(inv.name for inv in invoice_list),
		)

	expense_columns = [(account + ":Currency/currency:120") for account in expense_accounts]
	unrealized_profit_loss_account_columns = [
		(account + ":Currency/currency:120") for account in unrealized_profit_loss_accounts
	]

	tax_columns = [
		(account + ":Currency/currency:120")
		for account in tax_accounts
		if account not in expense_accounts
	]

	columns = (
		columns
		+ expense_columns
		+ unrealized_profit_loss_account_columns
		+ [_("Net Total") + ":Currency/currency:120"]
		+ tax_columns
		+ [
			_("Total Tax") + ":Currency/currency:120",
			_("Grand Total") + ":Currency/currency:120",
			_("Rounded Total") + ":Currency/currency:120",
			_("Outstanding Amount") + ":Currency/currency:120",
		]
	)

	return columns, expense_accounts, tax_accounts, unrealized_profit_loss_accounts


def get_conditions(filters, payments=False):
	conditions = ""

	if filters.get("company"):
		conditions += " and company=%(company)s"
	if filters.get("supplier"):
		conditions += " and party = %(supplier)s" if payments else " and supplier = %(supplier)s"

	if filters.get("from_date"):
		conditions += " and posting_date>=%(from_date)s"
	if filters.get("to_date"):
		conditions += " and posting_date<=%(to_date)s"

	if filters.get("mode_of_payment"):
		conditions += " and ifnull(mode_of_payment, '') = %(mode_of_payment)s"

	if filters.get("cost_center"):
		if payments:
			conditions += " and cost_center = %(cost_center)s"
		else:
			conditions += """ and exists(select name from `tabPurchase Invoice Item`
				where parent=`tabPurchase Invoice`.name
					and ifnull(`tabPurchase Invoice Item`.cost_center, '') = %(cost_center)s)"""

	if filters.get("warehouse") and not payments:
		conditions += """ and exists(select name from `tabPurchase Invoice Item`
			 where parent=`tabPurchase Invoice`.name
			 	and ifnull(`tabPurchase Invoice Item`.warehouse, '') = %(warehouse)s)"""

	if filters.get("item_group") and not payments:
		conditions += """ and exists(select name from `tabPurchase Invoice Item`
			 where parent=`tabPurchase Invoice`.name
			 	and ifnull(`tabPurchase Invoice Item`.item_group, '') = %(item_group)s)"""

	accounting_dimensions = get_accounting_dimensions(as_list=False)

	if accounting_dimensions:
		common_condition = """
			and exists(select name from `tabPurchase Invoice Item`
				where parent=`tabPurchase Invoice`.name
			"""
		for dimension in accounting_dimensions:
			if filters.get(dimension.fieldname):
				if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
					filters[dimension.fieldname] = get_dimension_with_children(
						dimension.document_type, filters.get(dimension.fieldname)
					)

					conditions += (
						common_condition
						+ "and ifnull(`tabPurchase Invoice`.{0}, '') in %({0})s)".format(dimension.fieldname)
					)
				else:
					conditions += (
						common_condition
						+ "and ifnull(`tabPurchase Invoice`.{0}, '') in %({0})s)".format(dimension.fieldname)
					)

	return conditions


def get_invoices(filters, additional_query_columns):
	conditions = get_conditions(filters)
	return frappe.db.sql(
		"""
		select
			'Purchase Invoice' as doctype, name, posting_date, credit_to, supplier, supplier_name, tax_id, bill_no, bill_date,
			remarks, base_net_total, base_grand_total, outstanding_amount,
			mode_of_payment {0}
		from `tabPurchase Invoice`
		where docstatus = 1 {1}
		order by posting_date desc, name desc""".format(
			additional_query_columns, conditions
		),
		filters,
		as_dict=1,
	)


def get_payments(filters, additional_query_columns):
	if additional_query_columns:
		additional_query_columns = ", " + ", ".join(additional_query_columns)

	conditions = get_conditions(filters, payments=True)
	args = frappe._dict(
		account="credit_to",
		party="supplier",
		party_name="supplier_name",
		additional_query_columns="" if not additional_query_columns else additional_query_columns,
		party_type="Supplier",
		conditions=conditions,
	)
	payment_entries = get_payment_entries(filters, args)
	journal_entries = get_journal_entries(filters, args)
	return payment_entries + journal_entries


def get_invoice_expense_map(invoice_list):
	expense_details = frappe.db.sql(
		"""
		select parent, expense_account, sum(base_net_amount) as amount
		from `tabPurchase Invoice Item`
		where parent in (%s)
		group by parent, expense_account
	"""
		% ", ".join(["%s"] * len(invoice_list)),
		tuple(inv.name for inv in invoice_list),
		as_dict=1,
	)

	invoice_expense_map = {}
	for d in expense_details:
		invoice_expense_map.setdefault(d.parent, frappe._dict()).setdefault(d.expense_account, [])
		invoice_expense_map[d.parent][d.expense_account] = flt(d.amount)

	return invoice_expense_map


def get_internal_invoice_map(invoice_list):
	unrealized_amount_details = frappe.db.sql(
		"""SELECT name, unrealized_profit_loss_account,
		base_net_total as amount from `tabPurchase Invoice` where name in (%s)
		and is_internal_supplier = 1 and company = represents_company"""
		% ", ".join(["%s"] * len(invoice_list)),
		tuple(inv.name for inv in invoice_list),
		as_dict=1,
	)

	internal_invoice_map = {}
	for d in unrealized_amount_details:
		if d.unrealized_profit_loss_account:
			internal_invoice_map.setdefault((d.name, d.unrealized_profit_loss_account), d.amount)

	return internal_invoice_map


def get_invoice_tax_map(
	invoice_list, invoice_expense_map, expense_accounts, include_payments=False
):
	tax_details = frappe.db.sql(
		"""
		select parent, account_head, case add_deduct_tax when "Add" then sum(base_tax_amount_after_discount_amount)
		else sum(base_tax_amount_after_discount_amount) * -1 end as tax_amount
		from `tabPurchase Taxes and Charges`
		where parent in (%s) and category in ('Total', 'Valuation and Total')
			and base_tax_amount_after_discount_amount != 0
		group by parent, account_head, add_deduct_tax
	"""
		% ", ".join(["%s"] * len(invoice_list)),
		tuple(inv.name for inv in invoice_list),
		as_dict=1,
	)

	if include_payments:
		advance_tax_details = frappe.db.sql(
			"""
			select parent, account_head, case add_deduct_tax when "Add" then sum(base_tax_amount)
			else sum(base_tax_amount) * -1 end as tax_amount
			from `tabAdvance Taxes and Charges`
			where parent in (%s) and charge_type in ('On Paid Amount', 'Actual')
				and base_tax_amount != 0
			group by parent, account_head, add_deduct_tax
		"""
			% ", ".join(["%s"] * len(invoice_list)),
			tuple(inv.name for inv in invoice_list),
			as_dict=1,
		)
		tax_details += advance_tax_details

	invoice_tax_map = {}
	for d in tax_details:
		if d.account_head in expense_accounts:
			if d.account_head in invoice_expense_map[d.parent]:
				invoice_expense_map[d.parent][d.account_head] += flt(d.tax_amount)
			else:
				invoice_expense_map[d.parent][d.account_head] = flt(d.tax_amount)
		else:
			invoice_tax_map.setdefault(d.parent, frappe._dict()).setdefault(d.account_head, [])
			invoice_tax_map[d.parent][d.account_head] = flt(d.tax_amount)

	return invoice_expense_map, invoice_tax_map


def get_invoice_po_pr_map(invoice_list):
	pi_items = frappe.db.sql(
		"""
		select parent, purchase_order, purchase_receipt, po_detail, project
		from `tabPurchase Invoice Item`
		where parent in (%s)
	"""
		% ", ".join(["%s"] * len(invoice_list)),
		tuple(inv.name for inv in invoice_list),
		as_dict=1,
	)

	invoice_po_pr_map = {}
	for d in pi_items:
		if d.purchase_order:
			invoice_po_pr_map.setdefault(d.parent, frappe._dict()).setdefault("purchase_order", []).append(
				d.purchase_order
			)

		pr_list = None
		if d.purchase_receipt:
			pr_list = [d.purchase_receipt]
		elif d.po_detail:
			pr_list = frappe.db.sql_list(
				"""select distinct parent from `tabPurchase Receipt Item`
				where docstatus=1 and purchase_order_item=%s""",
				d.po_detail,
			)

		if pr_list:
			invoice_po_pr_map.setdefault(d.parent, frappe._dict()).setdefault("purchase_receipt", pr_list)

		if d.project:
			invoice_po_pr_map.setdefault(d.parent, frappe._dict()).setdefault("project", []).append(
				d.project
			)

	return invoice_po_pr_map


def get_account_details(invoice_list):
	account_map = {}
	accounts = list(set([inv.credit_to for inv in invoice_list]))
	for acc in frappe.db.sql(
		"""select name, parent_account from tabAccount
		where name in (%s)"""
		% ", ".join(["%s"] * len(accounts)),
		tuple(accounts),
		as_dict=1,
	):
		account_map[acc.name] = acc.parent_account

	return account_map
