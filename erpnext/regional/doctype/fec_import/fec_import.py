# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import datetime
from collections import defaultdict

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.csvutils import read_csv_content


class FECImport(Document):
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

		FECImporter(settings=self, data=output)


class FECImporter:
	def __init__(self, settings, data):
		self.settings = settings
		self.company_settings = {}
		if frappe.db.exists("FEC Import Settings", dict(company=self.settings.company)):
			self.company_settings = frappe.get_doc(
				"FEC Import Settings", dict(company=self.settings.company)
			)

		self.data = data

		self.import_data()

	def import_data(self):
		self.get_journals_mapping()
		self.group_data()
		self.get_accounts_data()
		self.create_document()
		self.insert_documents()

	def group_data(self):
		initial_group = defaultdict(list)
		self.grouped_data = defaultdict(lambda: defaultdict(list))

		for d in self.data:
			if not frappe.db.exists("GL Entry", dict(accounting_entry_number=d.EcritureNum)):
				initial_group[d["EcritureNum"]].append(frappe._dict(d))

		for ecriturenum in initial_group:
			if [line.CompAuxNum for line in initial_group[ecriturenum]]:
				journal_type = frappe.get_cached_value(
					"Accounting Journal", initial_group[ecriturenum][0].JournalCode, "type"
				)
				if journal_type == "Sales":
					self.grouped_data["Sales Invoice"][ecriturenum] = initial_group[ecriturenum]
				elif journal_type == "Purchase":
					self.grouped_data["Purchase Invoice"][ecriturenum] = initial_group[ecriturenum]

			else:
				self.grouped_data["Journal Entry"][ecriturenum] = initial_group[ecriturenum]

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

		for ecriturenum in self.grouped_data["Journal Entry"]:
			self.create_journal_entry(ecriturenum)

		for ecriturenum in self.grouped_data["Sales Invoice"]:
			self.create_sales_invoice(ecriturenum)

		for ecriturenum in self.grouped_data["Purchase Invoice"]:
			self.create_purchase_invoice(ecriturenum)

	def create_journal_entry(self, ecriturenum):
		journal_entry = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": self.settings.company,
				"posting_date": datetime.datetime.strptime(
					self.grouped_data[ecriturenum][0].EcritureDate, "%Y%m%d"
				).strftime("%Y-%m-%d"),
				"cheque_no": ecriturenum,
			}
		)
		for line in self.grouped_data[ecriturenum]:
			journal_code = self.journals.get(line["JournalCode"])

			compte_aux = line.CompAuxNum
			compte_aux_type = None
			if compte_aux:
				journal_type = frappe.get_cached_value("Accounting Journal", journal_code, "type")
				if journal_type == "Sales":
					compte_aux = frappe.db.exists("Customer", compte_aux)
					compte_aux_type = "Customer"
				elif journal_type == "Purchase":
					compte_aux = frappe.db.exists("Supplier", compte_aux)
					compte_aux_type = "Supplier"

			journal_entry.append(
				"accounts",
				{
					"accounting_journal": journal_code,
					"account": self.accounts.get(line["CompteNum"]),
					"debit_in_account_currency": flt(line["Debit"].replace(",", ".")),
					"credit_in_account_currency": flt(line["Credit"].replace(",", ".")),
					"user_remark": line.EcritureLib,
					"reference_name": line.PieceRef,
					"party_type": compte_aux_type if compte_aux_type and compte_aux else None,
					"party": compte_aux if compte_aux_type and compte_aux else None,
				},
			)
		journal_entry.flags.accounting_entry_number = line.EcritureNum

		self.journal_entries.append(journal_entry)

	def create_sales_invoice(self, ecriturenum):
		pass

	def create_purchase_invoice(self, ecriturenum):
		pass

	def insert_documents(self):
		print(self.journal_entries[0].as_dict())
		self.journal_entries[0].insert()
