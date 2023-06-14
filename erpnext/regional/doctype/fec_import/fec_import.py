# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import codecs
import datetime
import hashlib
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate
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
		data = self.get_data()

		try:
			import_in_progress = FECImportDocumentCreator(settings=self, data=data)
			import_in_progress.import_data()
		except Exception:
			print(frappe.get_traceback())

	def get_data(self):
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
					if head.__contains__(codecs.BOM_UTF8.decode("utf-8")):
						# A Byte Order Mark is present
						head = head.strip(codecs.BOM_UTF8.decode("utf-8"))
					row[head] = d[count] or ""

			output.append(row)

		return output

	@frappe.whitelist()
	def create_journals(self):
		journals = {l["JournalCode"]: l["JournalLib"] for l in self.get_data()}

		for journal in journals:
			doc = frappe.new_doc("Accounting Journal")
			doc.journal_code = journal
			doc.journal_name = journals[journal]
			doc.insert(ignore_if_duplicate=True)

	@frappe.whitelist()
	def create_accounts(self):
		accounts = {l["CompteNum"]: l["CompteLib"] for l in self.get_data()}
		account_groups = frappe.get_all(
			"Account",
			filters={
				"disabled": 0,
				"is_group": 1,
				"account_number": ("is", "set"),
				"company": self.company,
				"do_not_show_account_number": 0,
			},
			fields=["name", "parent_account", "account_number"],
		)
		accounts_with_number_list = [x.name for x in account_groups]

		account_groups_with_numbers = {}
		for group in account_groups:
			if not group.parent_account in accounts_with_number_list:
				account_groups_with_numbers.update({group.account_number[:-1]: group.parent_account})
			account_groups_with_numbers.update({group.account_number: group.name})

		for account in accounts:
			if not frappe.db.exists("Account", dict(account_number=account)):
				doc = frappe.new_doc("Account")
				doc.account_name = accounts[account]
				doc.account_number = account
				doc.parent_account = self.get_parent_account(account_groups_with_numbers, account)
				doc.insert(ignore_if_duplicate=True)

	def get_parent_account(self, account_groups, account):
		if frappe.db.exists(
			"Account", dict(account_number=str(account)[:-1], disabled=0, company=self.company)
		) and account_groups.get(account[:-1]):
			return account_groups.get(account[:-1])

		account_numbers = [key for key, value in account_groups.items()]
		for idx, acc in enumerate(account):
			sub_number = account[:idx]
			if sub_number in account_numbers:
				continue
			elif account_groups.get(account[: idx - 1]):
				return account_groups[account[: idx - 1]]

		root_mapping = {
			"1": "Equity",
			"2": "Asset",
			"3": "Asset",
			"4": "Liability",
			"5": "Equity",
			"6": "Expense",
			"7": "Income",
		}

		return frappe.db.get_value(
			"Account",
			dict(
				disabled=0,
				root_type=root_mapping.get(str(account)[0]),
				company=self.company,
				parent_account=("is", "not set"),
			),
		)


class FECImportDocumentCreator:
	def __init__(self, settings, data):
		self.settings = settings
		self.company_settings = frappe.db.get_value(
			"FEC Import Settings", dict(company=self.settings.company)
		)
		if not self.company_settings:
			frappe.throw(
				_("Please configure a FEC Import Settings document for company {0}").format(
					self.settings.company
				)
			)

		self.data = data

	def import_data(self):
		self.group_data()
		self.create_fec_import_documents()
		self.process_fec_import_documents()

	def group_data(self):
		self.grouped_data = defaultdict(lambda: defaultdict(list))
		accounting_journals = self.get_accounting_journals_mapping()

		for d in self.data:
			if not self.is_within_date_range(d):
				continue

			if (
				self.settings.import_journal
				and not accounting_journals.get(d.get("JournalCode")) == self.settings.import_journal
			):
				continue

			self.grouped_data[d["EcritureDate"]][d["PieceRef"]].append(frappe._dict(d))

	@staticmethod
	def parse_credit_debit(d):
		d["Debit"] = flt(d["Debit"].replace(",", "."))
		d["Credit"] = flt(d["Credit"].replace(",", "."))
		d["Montantdevise"] = flt(d["Montantdevise"].replace(",", "."))

	def create_fec_import_documents(self):
		for date in self.grouped_data:
			for piece in self.grouped_data[date]:
				iter_next = False
				doc = frappe.new_doc("FEC Import Document")
				doc.fec_import = self.settings.name
				doc.settings = self.company_settings
				doc.gl_entries_date = datetime.datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
				doc.gl_entry_reference = piece

				for line in self.grouped_data[date][piece]:
					concatenated_data = "".join([value for key, value in line.items()])
					self.parse_credit_debit(line)
					row = {frappe.scrub(key): value for key, value in line.items()}
					row["hashed_data"] = hash_line(concatenated_data)

					if frappe.db.exists("FEC Import Line", dict(hashed_data=row["hashed_data"])):
						iter_next = True
						break

					doc.append("gl_entries", row)

				if iter_next:
					continue

				doc.insert()

	def process_fec_import_documents(self):
		groups = {"Transaction": [], "Payment": [], "Miscellaneous": []}

		for doc in frappe.get_all(
			"FEC Import Document",
			filters={"status": "Pending"},
			fields=["name", "import_type"],
			order_by="gl_entries_date",
		):
			groups[doc.import_type].append(doc.name)

		for group in ["Transaction", "Miscellaneous", "Payment"]:
			for d in groups[group]:
				frappe.get_doc("FEC Import Document", d).run_method("process_document_in_background")

	def is_within_date_range(self, line):
		posting_date = datetime.datetime.strptime(line.EcritureDate, "%Y%m%d").strftime("%Y-%m-%d")

		if self.settings.from_date and getdate(posting_date) < getdate(self.settings.from_date):
			return False

		if self.settings.to_date and getdate(posting_date) > getdate(self.settings.to_date):
			return False

		return True

	def get_accounting_journals_mapping(self):
		dokos_journals = {
			x.journal_code: x.name
			for x in frappe.get_all(
				"Accounting Journal", filters={"disabled": 0}, fields=["journal_code", "name"]
			)
		}

		company_settings = frappe.get_doc("FEC Import Settings", self.company_settings)

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


def hash_line(data):
	sha = hashlib.sha256()
	sha.update(frappe.safe_encode(str(data)))
	return sha.hexdigest()
