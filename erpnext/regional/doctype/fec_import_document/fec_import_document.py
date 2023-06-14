# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_year_ending, get_year_start, getdate
from tenacity import retry, retry_if_result, stop_after_attempt

from erpnext.accounts.utils import FiscalYearError, get_fiscal_years


def value_is_true(value):
	return value is True


class FECImportDocument(Document):
	def validate(self):
		if self.status != "Completed":
			for row in self.gl_entries:
				self.get_accounting_journal(row)
				self.get_gl_account(row)
				self.get_party(row)
				self.parse_dates(row)

	def before_insert(self):
		self.set_import_type()

	def set_import_type(self):
		if self.is_payment_entry():
			self.import_type = "Payment"
		elif [l.party for l in self.gl_entries if l.party]:
			self.import_type = "Transaction"
		else:
			self.import_type = "Miscellaneous"

	def check_fiscal_year(self):
		try:
			posting_date = getdate(self.gl_entries_date)
			get_fiscal_years(posting_date)
		except FiscalYearError:
			# TODO: Create Fiscal Year based on FEC file name
			frappe.clear_messages()
			doc = frappe.get_doc(
				{
					"doctype": "Fiscal Year",
					"year": posting_date.year,
					"year_start_date": get_year_start(posting_date),
					"year_end_date": get_year_ending(posting_date),
				}
			)
			doc.insert(ignore_if_duplicate=True)

	def get_accounting_journal(self, row):
		if row.accounting_journal:
			return

		journals = self.get_accounting_journals_mapping()
		row.accounting_journal = journals.get(row.journalcode)

	def get_accounting_journals_mapping(self):
		dokos_journals = {
			x.journal_code: x.name
			for x in frappe.get_all(
				"Accounting Journal", filters={"disabled": 0}, fields=["journal_code", "name"]
			)
		}

		company_settings = frappe.get_doc("FEC Import Settings", self.settings)

		journals = {}
		mapped_journals = dokos_journals
		for mapping in company_settings.get("accounting_journal_mapping", []):
			for j in mapped_journals:
				if j == mapping.accounting_journal_in_dokos:
					journals[mapping.accounting_journal_in_fec] = mapped_journals[j]
					continue

				journals[j] = mapped_journals[j]

			mapped_journals = journals

		return journals or dokos_journals

	def get_gl_account(self, row):
		if row.account:
			return

		accounts = {
			x.account_number.strip(): x.name
			for x in frappe.get_all(
				"Account",
				filters={"disabled": 0, "account_number": ("is", "set")},
				fields=["name", "account_number"],
			)
		}

		row.account = accounts.get(row.comptenum)

	def get_party(self, row):
		if not row.compauxnum or (row.party_type and row.party):
			return

		journal_type = frappe.get_cached_value("Accounting Journal", row.accounting_journal, "type")
		account_type = frappe.get_cached_value("Account", row.account, "account_type")

		compte_aux = None
		compte_aux_type = None
		if journal_type in ("Sales", "Bank") or account_type == "Receivable":
			if compte_aux := frappe.db.exists("Customer", row.compauxnum):
				compte_aux_type = "Customer"
		elif journal_type in ("Purchase", "Bank") or account_type == "Payable":
			if compte_aux := frappe.db.exists("Supplier", row.compauxnum):
				compte_aux_type = "Supplier"

		if account_type in ["Receivable", "Payable"] and not (compte_aux and compte_aux_type):
			if account_type == "Receivable":
				compte_aux_type = "Customer"
				compte_aux = self.create_customer(compte_aux, row.compauxlib)
			else:
				compte_aux_type = "Supplier"
				compte_aux = self.create_supplier(compte_aux, row.compauxlib)

		row.party_type = compte_aux_type
		row.party = compte_aux

	def create_customer(self, compauxnum, compauxlib):
		company_settings = frappe.get_doc("FEC Import Settings", self.settings)

		customer = frappe.new_doc("Customer")
		customer.name = compauxnum
		customer.customer_name = compauxlib
		customer.customer_group = company_settings.customer_group or frappe.db.get_single_value(
			"Selling Settings", "customer_group"
		)
		customer.territory = company_settings.territory or frappe.db.get_single_value(
			"Selling Settings", "territory"
		)

		frappe.flags.in_import = True
		customer.flags.name_set = True
		customer.insert(ignore_if_duplicate=True)
		frappe.flags.in_import = False

		return customer.name

	def create_supplier(self, compauxnum, compauxlib):
		company_settings = frappe.get_doc("FEC Import Settings", self.settings)

		supplier = frappe.new_doc("Supplier")
		supplier.name = compauxnum
		supplier.supplier_name = compauxlib
		supplier.supplier_group = company_settings.supplier_group or frappe.db.get_single_value(
			"Buying Settings", "supplier_group"
		)

		frappe.flags.in_import = True
		supplier.flags.name_set = True
		supplier.insert(ignore_if_duplicate=True)
		frappe.flags.in_import = False

		return supplier.name

	def parse_dates(self, row):
		row.posting_date = parse_date(row.ecrituredate)
		row.transaction_date = parse_date(row.piecedate)
		row.validation_date = parse_date(row.validdate)
		row.reconciliation_date = parse_date(row.datelet)

	@frappe.whitelist()
	def create_linked_document(self):
		fields = ["accounting_journal", "account"]
		for line in self.gl_entries:
			for field in fields:
				if not line.get(field):
					frappe.throw(
						_(
							"Row #{0}: Data for field {1} could not be found automatically. Please select it manually"
						).format(line.idx, frappe.unscrub(field))
					)

		return self.create_references()

	def process_document_in_background(self, defer_payments=False):
		frappe.enqueue_doc(
			self.doctype, self.name, "create_references", defer_payments=defer_payments, timeout=1000
		)

	@retry(stop=stop_after_attempt(5), retry=retry_if_result(value_is_true))
	def create_references(self, defer_payments=False):
		self.db_set("status", "Pending")
		self.db_set("error", None)
		try:
			self.check_fiscal_year()
			company_settings = frappe.get_doc("FEC Import Settings", self.settings)

			party = [l.party for l in self.gl_entries if l.party]
			party_type = [l.party_type for l in self.gl_entries if l.party_type]
			if len(party) == 1 and len(party_type) == 1:
				if not self.is_payment_entry():
					if company_settings.create_sales_invoices and party_type[0] == "Customer":
						self.create_sales_invoice()
					elif company_settings.create_sales_invoices and party_type[0] == "Supplier":
						self.create_purchase_invoice()
					else:
						self.create_journal_entry()
				else:
					self.create_journal_entry(True if defer_payments else False)
			else:
				self.create_journal_entry()
		except Exception:
			self.db_set("status", "Error")
			self.db_set("error", frappe.get_traceback())

			if defer_payments:
				return True

	def create_journal_entry(self, payment_entry=False):
		journal_entry = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": self.company,
				"posting_date": self.gl_entries_date,
				"cheque_no": self.gl_entry_reference,
				"cheque_date": self.gl_entries_date,
			}
		)
		for line in self.gl_entries:
			self.check_account_is_not_a_group(line.account)
			reference_type, reference_name = self.get_payment_references(line)
			journal_entry.append(
				"accounts",
				{
					"accounting_journal": line.accounting_journal,
					"account": line.account,
					"debit_in_account_currency": line.debit,
					"debit": line.debit,
					"credit_in_account_currency": line.credit,
					"credit": line.credit,
					"user_remark": f"{line.ecriturelib}<br>{line.pieceref}",
					"reference_type": reference_type,
					"reference_name": reference_name,
					"party_type": line.party_type,
					"party": line.party,
				},
			)

		if payment_entry and not reference_type and not reference_name:
			frappe.throw(_("Payment references could not be found"))

		if journal_entry.accounts:
			if self.gl_entry_reference:
				journal_entry.name = self.gl_entry_reference
				journal_entry.flags.draft_name_set = True
			journal_entry.insert()

			if frappe.db.get_value("FEC Import Settings", self.settings, "submit_journal_entries"):
				journal_entry.submit()

			self.db_set("linked_document_type", "Journal Entry")
			self.db_set("linked_document", journal_entry.name)
			self.db_set("status", "Completed")

	def is_payment_entry(self):
		return [line.ecriturelet for line in self.gl_entries if line.ecriturelet] and [
			l.account
			for l in self.gl_entries
			if frappe.get_cached_value("Account", l.account, "account_type") in ["Bank", "Cash"]
		]

	def get_payment_references(self, line):
		reference_type, reference_name = None, None
		if line.ecriturelet:
			filters = dict(
				name=("!=", line.name),
				ecriturelet=line.ecriturelet,
				comptenum=line.comptenum,
				compauxnum=line.compauxnum,
				datelet=line.datelet,
			)

			if flt(line.credit) > 0.0:
				filters["debit"] = (">", 0.0)
			else:
				filters["credit"] = (">", 0.0)

			for doc in frappe.get_all("FEC Import Line", filters=filters, pluck="parent"):
				reference_type, reference_name = frappe.db.get_value(
					"FEC Import Document", doc, ["linked_document_type", "linked_document"]
				)

		return reference_type, reference_name

	def create_sales_invoice(self):
		customer, debit_to, remark = self.get_party_and_party_account()

		sales_invoice = frappe.new_doc("Sales Invoice")
		sales_invoice.flags.ignore_permissions = True
		sales_invoice.update(
			{
				"company": self.company,
				"posting_date": self.gl_entries_date,
				"set_posting_time": 1,
				"customer": customer,
				"debit_to": debit_to,
				"accounting_journal": self.gl_entries[0].accounting_journal,
				"remarks": remark,
				"due_date": self.gl_entries_date,
			}
		)

		self.add_items(sales_invoice)
		self.add_taxes(sales_invoice)
		sales_invoice.set_missing_values()

		if sales_invoice.customer and sales_invoice.items:
			# self.sales_invoices.append(sales_invoice)
			try:
				if self.gl_entry_reference:
					sales_invoice.name = self.gl_entry_reference
					sales_invoice.flags.draft_name_set = True
				sales_invoice.insert()

				if frappe.db.get_value("FEC Import Settings", self.settings, "submit_sales_invoices"):
					if self.gl_entry_reference:
						sales_invoice.flags.name_set = True

					sales_invoice.flags.ignore_version = True
					sales_invoice.submit()

				self.db_set("linked_document_type", "Sales Invoice")
				self.db_set("linked_document", sales_invoice.name)
				self.db_set("status", "Completed")
			except frappe.DuplicateEntryError:
				print("Duplicate Invoice", sales_invoice.name)
				self.db_set("linked_document_type", "Sales Invoice")
				self.db_set("linked_document", sales_invoice.name)
				self.db_set("status", "Completed")

		else:
			self.create_journal_entry()

	def create_purchase_invoice(self):
		supplier, credit_to, remark = self.get_party_and_party_account()

		purchase_invoice = frappe.new_doc("Purchase Invoice")
		purchase_invoice.flags.ignore_permissions = True
		purchase_invoice.update(
			{
				"company": self.company,
				"posting_date": self.gl_entries_date,
				"set_posting_time": 1,
				"supplier": supplier,
				"credit_to": credit_to,
				"accounting_journal": self.gl_entries[0].accounting_journal,
				"remarks": remark,
			}
		)

		self.add_items(purchase_invoice)
		self.add_taxes(purchase_invoice)
		purchase_invoice.set_missing_values()

		if purchase_invoice.supplier and purchase_invoice.items:
			# self.purchase_invoices.append(purchase_invoice)
			try:
				if self.gl_entry_reference:
					purchase_invoice.name = self.gl_entry_reference
					purchase_invoice.flags.draft_name_set = True
				purchase_invoice.insert()

				if frappe.db.get_value("FEC Import Settings", self.settings, "submit_sales_invoices"):
					if self.gl_entry_reference:
						purchase_invoice.flags.name_set = True

					purchase_invoice.flags.ignore_version = True
					purchase_invoice.submit()

				self.db_set("linked_document_type", "Purchase Invoice")
				self.db_set("linked_document", purchase_invoice.name)
				self.db_set("status", "Completed")
			except frappe.DuplicateEntryError:
				print("Duplicate Invoice", purchase_invoice.name)
				self.db_set("linked_document_type", "Purchase Invoice")
				self.db_set("linked_document", purchase_invoice.name)
				self.db_set("status", "Completed")

		else:
			self.create_journal_entry()

	def get_party_and_party_account(self):
		party_name = None
		party_account = None
		party_remark = None
		for line in self.gl_entries:
			if line.comptenum.startswith("40") or line.comptenum.startswith("41"):
				if line.compauxnum:
					party_name = line.party

				party_account = line.account
				party_remark = line.ecriturelib

				break

		return party_name, party_account, party_remark

	def add_items(self, transaction):
		for line in self.gl_entries:
			if (
				(line.comptenum.startswith("6") and line.debit > 0.0)
				if transaction.doctype == "Purchase Invoice"
				else (line.comptenum.startswith("7") and line.credit > 0.0)
			):
				transaction.append(
					"items",
					{
						"item_code": frappe.db.get_value(
							"FEC Import Settings",
							self.settings,
							"purchase_item" if transaction.doctype == "Purchase Invoice" else "sales_item",
						),
						"qty": 1,
						"rate": line.credit if transaction.doctype == "Sales Invoice" else line.debit,
						"income_account": line.account if transaction.doctype == "Sales Invoice" else None,
						"expense_account": line.account if transaction.doctype == "Purchase Invoice" else None,
						"remarks": line.ecriturelib,
					},
				)

				self.check_account_is_not_a_group(line.account)

	def add_taxes(self, transaction):
		for line in self.gl_entries:
			if (
				(line.comptenum.startswith("6") and line.debit > 0.0)
				if transaction.doctype == "Purchase Invoice"
				else (line.comptenum.startswith("7") and line.credit > 0.0)
			):
				continue

			if line.comptenum.startswith("40") or line.comptenum.startswith("41"):
				continue

			amount = 0.0
			if transaction.doctype == "Sales Invoice":
				amount = line.credit
				if not amount:
					amount = flt(line.debit) * -1

			elif transaction.doctype == "Purchase Invoice":
				amount = flt(line.debit)
				if not amount:
					amount = flt(line.credit) * -1

			transaction.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": line.account,
					"tax_amount": amount,
					"description": line.ecriturelib,
				},
			)

			self.check_account_is_not_a_group(line.account)

	def check_account_is_not_a_group(self, account):
		if frappe.db.get_value("Account", account, "is_group"):
			frappe.db.set_value("Account", account, "is_group", 0)


def parse_date(date):
	if not date:
		return

	return datetime.datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")


@frappe.whitelist()
def bulk_process(docnames):
	docnames = frappe.parse_json(docnames)
	for docname in docnames:
		doc = frappe.get_doc("FEC Import Document", docname)
		if doc.status != "Completed":
			doc.run_method("process_document_in_background")
