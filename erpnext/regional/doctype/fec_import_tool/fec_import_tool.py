# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import datetime
from collections import defaultdict

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate
from frappe.utils.csvutils import read_csv_content


class FECImportTool(Document):
	@frappe.whitelist()
	def get_company(self):
		company = None
		if self.fec_file:
			file_name = frappe.db.get_value(
				"File",
				{
					"file_url": self.fec_file,
					"attached_to_doctype": self.doctype,
					"attached_to_name": self.name,
				},
				"file_name",
			)
			try:
				if siren := file_name.split("FEC")[0]:
					return frappe.db.get_value("Company", dict(siren_number=siren))
			except Exception:
				return company

		return company

	@frappe.whitelist()
	def upload_fec(self):
		fileid = frappe.db.get_value(
			"File",
			{"file_url": self.fec_file, "attached_to_doctype": self.doctype, "attached_to_name": self.name},
		)

		_file = frappe.get_doc("File", fileid)
		fcontent = _file.get_content()
		rows = read_csv_content(fcontent, delimiter="\t")

		header = rows[0]
		data = rows[1:]

		output = list()
		for d in data:
			row = frappe._dict()
			for count, head in enumerate(header):
				if head:
					row[head] = d[count] or ""

			output.append(row)

		try:
			print("START IMPORT")
			import_in_progress = FECImport(settings=self, data=output)
			import_in_progress.import_data()
		except Exception:
			print(frappe.get_traceback())


class FECImport:
	def __init__(self, settings, data):
		self.settings = settings
		self.company_settings = {}
		if frappe.db.exists("FEC Import Settings", dict(company=self.settings.company)):
			self.company_settings = frappe.get_doc(
				"FEC Import Settings", dict(company=self.settings.company)
			)

		self.data = data

	def import_data(self):
		self.get_journals_mapping()
		self.parse_credit_debit()
		self.group_data()
		self.get_accounts_data()
		self.create_document()
		# self.insert_transactional_documents()

	def group_data(self):
		initial_group = defaultdict(list)
		self.grouped_data = defaultdict(lambda: defaultdict(list))
		self.payment_data = defaultdict(tuple)

		for d in self.data:
			# if not frappe.db.exists("GL Entry", dict(accounting_entry_number=d.EcritureNum)):
			initial_group[d["EcritureNum"]].append(frappe._dict(d))

		for ecriturenum in initial_group:
			if [line.CompAuxNum for line in initial_group[ecriturenum] if line.CompAuxNum]:

				# if not self.is_within_date_range(initial_group[ecriturenum][0]):
				# 	continue

				journal_type = frappe.get_cached_value(
					"Accounting Journal", initial_group[ecriturenum][0].JournalCode, "type"
				)

				if self.company_settings.create_sales_invoices and journal_type == "Sales":
					self.grouped_data["Sales Invoice"][ecriturenum] = initial_group[ecriturenum]
				elif self.company_settings.create_purchase_invoices and journal_type == "Purchase":
					self.grouped_data["Purchase Invoice"][ecriturenum] = initial_group[ecriturenum]
				elif self.company_settings.create_payment_entries and journal_type == "Bank":
					self.grouped_data["Payment Entry"][ecriturenum] = initial_group[ecriturenum]
				else:
					self.grouped_data["Journal Entry"][ecriturenum] = initial_group[ecriturenum]

			else:
				self.grouped_data["Journal Entry"][ecriturenum] = initial_group[ecriturenum]

		# for a in self.grouped_data:
		# 	print("GROUPS")
		# 	print(a, len(self.grouped_data[a]))

	def parse_credit_debit(self):
		for d in self.data:
			d["Debit"] = flt(d["Debit"].replace(",", "."))
			d["Credit"] = flt(d["Credit"].replace(",", "."))

	def is_within_date_range(self, line):
		posting_date = datetime.datetime.strptime(line.EcritureDate, "%Y%m%d").strftime("%Y-%m-%d")

		if self.settings.from_date and getdate(posting_date) < getdate(self.settings.from_date):
			return False

		if self.settings.to_date and getdate(posting_date) > getdate(self.settings.to_date):
			return False

		return True

	def get_accounts_data(self):
		self.accounts = {
			x.account_number.strip(): x.name
			for x in frappe.get_all(
				"Account",
				filters={"disabled": 0, "account_number": ("is", "set")},
				fields=["name", "account_number"],
			)
		}

	def get_journals_mapping(self):
		dokos_journals = {
			x.journal_code: x.name
			for x in frappe.get_all(
				"Accounting Journal", filters={"disabled": 0}, fields=["journal_code", "name"]
			)
		}

		self.journals = {}
		mapped_journals = dokos_journals
		for mapping in self.company_settings.get("accounting_journal_mapping", []):
			for j in mapped_journals:
				if j == mapping.accounting_journal_in_dokos:
					self.journals[mapping.accounting_journal_in_fec] = mapped_journals[j]
					continue

				self.journals[j] = mapped_journals[j]

			mapped_journals = self.journals

	def create_document(self):
		self.journal_entries = []
		self.sales_invoices = []
		self.purchase_invoices = []
		self.payment_entries = []

		for ecriturenum in self.grouped_data["Sales Invoice"]:
			self.create_sales_invoice(ecriturenum, self.grouped_data["Sales Invoice"][ecriturenum])

		for ecriturenum in self.grouped_data["Purchase Invoice"]:
			self.create_purchase_invoice(ecriturenum, self.grouped_data["Purchase Invoice"][ecriturenum])

		for ecriturenum in self.grouped_data["Journal Entry"]:
			self.create_journal_entry(ecriturenum, self.grouped_data["Journal Entry"][ecriturenum])

		for ecriturenum in self.grouped_data["Payment Entry"]:
			self.create_journal_entry(ecriturenum, self.grouped_data["Journal Entry"][ecriturenum])

		print("payment_data", self.payment_data)

	def create_journal_entry(self, ecriturenum, rows):
		posting_date = datetime.datetime.strptime(rows[0].EcritureDate, "%Y%m%d").strftime("%Y-%m-%d")
		add_to_payment_data = None
		journal_entry = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": self.settings.company,
				"posting_date": posting_date,
				"cheque_no": ecriturenum,
				"cheque_date": posting_date,
			}
		)
		for line in rows:
			journal_code = self.journals.get(line["JournalCode"])

			if self.settings.import_journal and self.settings.import_journal != journal_code:
				continue

			reference_type, reference_name = None, None

			compte_aux = line.CompAuxNum
			compte_aux_type = None
			if compte_aux:
				journal_type = frappe.get_cached_value("Accounting Journal", journal_code, "type")
				account_type = frappe.get_cached_value(
					"Account", self.accounts.get(line["CompteNum"]), "account_type"
				)

				if journal_type in ("Sales", "Bank") or account_type == "Receivable":
					compte_aux = frappe.db.exists("Customer", compte_aux)
					compte_aux_type = "Customer"
				elif journal_type in ("Purchase", "Bank") or account_type == "Payable":
					compte_aux = frappe.db.exists("Supplier", compte_aux)
					compte_aux_type = "Supplier"

				if account_type in ["Receivable", "Payable"] and not (compte_aux and compte_aux_type):
					if line.EcritureLet and (reference := self.payment_data.get(line.EcritureLet)):
						reference_type = reference[0]
						reference_name = reference[1]

					elif line.EcritureLet:
						add_to_payment_data = line.EcritureLet

				if account_type in ["Receivable", "Payable"] and not (compte_aux and compte_aux_type):
					if account_type == "Receivable":
						compte_aux_type = "Customer"
						compte_aux = self.create_customer(compte_aux, line.CompAuxLib)
					else:
						compte_aux_type = "Supplier"
						compte_aux = self.create_supplier(compte_aux, line.CompAuxLib)

			journal_entry.append(
				"accounts",
				{
					"accounting_journal": journal_code,
					"account": self.accounts.get(line["CompteNum"]),
					"debit_in_account_currency": line["Debit"],
					"credit_in_account_currency": line["Credit"],
					"user_remark": f"{line.EcritureLib}<br>{line.PieceRef}",
					"reference_type": reference_type,
					"reference_name": reference_name,
					"party_type": compte_aux_type if compte_aux_type and compte_aux else None,
					"party": compte_aux if compte_aux_type and compte_aux else None,
				},
			)
		journal_entry.flags.accounting_entry_number = ecriturenum
		journal_entry.flags.ecriturenum = ecriturenum

		if journal_entry.accounts:
			journal_entry.insert()
			journal_entry.submit()

			if add_to_payment_data:
				self.payment_data[add_to_payment_data] = (journal_entry.doctype, journal_entry.name)

	def create_sales_invoice(self, ecriturenum, rows):
		invoicing_details = self.get_invoicing_details(rows, "Sales Invoice")
		posting_date = datetime.datetime.strptime(rows[0].EcritureDate, "%Y%m%d").strftime("%Y-%m-%d")

		sales_invoice = frappe.new_doc("Sales Invoice")
		sales_invoice.flags.ignore_permissions = True
		sales_invoice.flags.ecriturenum = ecriturenum
		sales_invoice.update(
			{
				"company": self.settings.company,
				"posting_date": posting_date,
				"set_posting_time": 1,
				"customer": invoicing_details.get("party_name"),
				"debit_to": invoicing_details.get("party_account"),
				"accounting_journal": self.journals.get(rows[0]["JournalCode"]),
				"remarks": invoicing_details.get("party_line", {}).get("EcritureLib"),
				"due_date": posting_date,
			}
		)

		self.add_items(sales_invoice, invoicing_details.get("items"), self.company_settings.sales_item)
		self.add_taxes(sales_invoice, invoicing_details.get("taxes"))
		sales_invoice.set_missing_values()

		if sales_invoice.customer and sales_invoice.items:
			# self.sales_invoices.append(sales_invoice)
			sales_invoice.insert()
			sales_invoice.submit()

			for ref in list(invoicing_details.get("references")):
				self.payment_data[ref] = (sales_invoice.doctype, sales_invoice.name)

		else:
			self.create_journal_entry(ecriturenum, rows)

	def create_purchase_invoice(self, ecriturenum, rows):
		invoicing_details = self.get_invoicing_details(rows, "Purchase Invoice")
		posting_date = datetime.datetime.strptime(rows[0].EcritureDate, "%Y%m%d").strftime("%Y-%m-%d")

		purchase_invoice = frappe.new_doc("Purchase Invoice")
		purchase_invoice.flags.ignore_permissions = True
		purchase_invoice.flags.ecriturenum = ecriturenum
		purchase_invoice.update(
			{
				"company": self.settings.company,
				"posting_date": posting_date,
				"set_posting_time": 1,
				"supplier": invoicing_details.get("party_name"),
				"credit_to": invoicing_details.get("party_account"),
				"accounting_journal": self.journals.get(rows[0]["JournalCode"]),
				"remarks": invoicing_details.get("party_line", {}).get("EcritureLib"),
			}
		)

		self.add_items(
			purchase_invoice, invoicing_details.get("items"), self.company_settings.sales_item
		)
		self.add_taxes(purchase_invoice, invoicing_details.get("taxes"))
		purchase_invoice.set_missing_values()

		if purchase_invoice.supplier and purchase_invoice.items:
			# self.purchase_invoices.append(purchase_invoice)
			purchase_invoice.insert()
			purchase_invoice.submit()

			for ref in list(invoicing_details.get("references")):
				self.payment_data[ref] = (purchase_invoice.doctype, purchase_invoice.name)

		else:
			self.create_journal_entry(ecriturenum, rows)

	def get_invoicing_details(self, lines, invoice_type):
		invoicing_details = {
			"party_account": "",
			"party_name": "",
			"party_line": {},
			"taxes": [],
			"items": [],
			"references": set(),
		}

		party_type = "Supplier" if invoice_type == "Purchase Invoice" else "Customer"

		for line in lines:
			if line.CompteNum.startswith("40") or line.CompteNum.startswith("41"):
				if line.CompAuxNum:
					invoicing_details["party_name"] = line["CompAuxNum"]

				invoicing_details["party_account"] = self.accounts.get(line["CompteNum"])
				invoicing_details["party_line"] = line

				if not invoicing_details["party_name"] or not frappe.db.exists(
					party_type, invoicing_details["party_name"]
				):
					invoicing_details["party_name"] = (
						self.create_supplier(line.CompAuxNum, line.CompAuxLib)
						if invoice_type == "Purchase Invoice"
						else self.create_customer(line.CompAuxNum, line.CompAuxLib)
					)

			elif (
				(line.CompteNum.startswith("6") and line.Debit > 0.0)
				if invoice_type == "Purchase Invoice"
				else (line.CompteNum.startswith("7") and line.Credit > 0.0)
			):
				invoicing_details["items"].append(line)

			else:
				invoicing_details["taxes"].append(line)

			if line.EcritureLet:
				invoicing_details["references"].add(line.EcritureLet)

		return invoicing_details

	def add_items(self, invoice_document, item_lines, item):
		for line in item_lines:
			invoice_document.append(
				"items",
				{
					"item_code": item,
					"qty": 1,
					"rate": line["Credit"]
					if invoice_document.get("doctype") == "Sales Invoice"
					else line["Debit"],
					"income_account": self.accounts.get(line["CompteNum"])
					if invoice_document.get("doctype") == "Sales Invoice"
					else None,
					"expense_account": self.accounts.get(line["CompteNum"])
					if invoice_document.get("doctype") == "Purchase Invoice"
					else None,
				},
			)

	def add_taxes(self, invoice_document, tax_lines):
		for line in tax_lines:
			amount = 0.0
			if invoice_document.get("doctype") == "Sales Invoice":
				amount = line["Credit"]
				if not amount:
					amount = flt(line["Debit"]) * -1

			elif invoice_document.get("doctype") == "Purchase Invoice":
				amount = flt(line["Debit"])
				if not amount:
					amount = flt(line["Credit"]) * -1

			invoice_document.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": self.accounts.get(line["CompteNum"]),
					"tax_amount": amount,
					"description": line.EcritureLib,
				},
			)

	def create_customer(self, compauxnum, compauxlib):
		customer = frappe.new_doc("Customer")
		customer.__newname = compauxnum
		customer.customer_name = compauxlib
		customer.customer_group = self.company_settings.customer_group or frappe.db.get_single_value(
			"Selling Settings", "customer_group"
		)
		customer.territory = self.company_settings.territory or frappe.db.get_single_value(
			"Selling Settings", "territory"
		)
		customer.insert()

		return customer.name

	def create_supplier(self, compauxnum, compauxlib):
		supplier = frappe.new_doc("Supplier")
		supplier.__newname = compauxnum
		supplier.supplier_name = compauxlib
		supplier.supplier_group = self.company_settings.supplier_group or frappe.db.get_single_value(
			"Buying Settings", "supplier_group"
		)
		supplier.insert()

		return supplier.name

	# def insert_transactional_documents(self):
	# 	print("journal_entries", len(self.journal_entries))
	# 	print("sales_invoices", len(self.sales_invoices))
	# 	print("purchase_invoices", len(self.purchase_invoices))

	# 	self.ecriturenum_map = {}

	# 	for journal_entry in self.journal_entries[:2]:
	# 		journal_entry.insert()
	# 		self.ecriturenum_map[journal_entry.flags.ecriturenum] = journal_entry.name

	# 	for sales_invoice in self.sales_invoices[:2]:
	# 		sales_invoice.insert()
	# 		self.ecriturenum_map[sales_invoice.flags.ecriturenum] = sales_invoice.name

	# 	for purchase_invoice in self.purchase_invoices[:2]:
	# 		purchase_invoice.insert()
	# 		self.ecriturenum_map[purchase_invoice.flags.ecriturenum] = purchase_invoice.name

	# 	print(self.ecriturenum_map)
