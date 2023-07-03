import json
import os
import re
import unittest
import xml.dom.minidom as minidom
from typing import Any

import frappe
from facturx import xml_check_xsd
from frappe.test_runner import make_test_objects
from frappe.tests.utils import FrappeTestCase

from ..common import types as t
from ..write.data import AddressInfo, ContactInfo, SellerInfo
from ..write.renderers import SalesInvoiceRenderer, TheTestRenderer


def idbg():
	from IPython.terminal.embed import InteractiveShellEmbed

	terminal = InteractiveShellEmbed()
	terminal.colors = "neutral"
	terminal.display_banner = False
	terminal()


def make_accounts(verbose=None):
	accounts = [
		# [account_name, parent_account, is_group]
		["_Test Bank", "Bank Accounts", 0, "Bank", None],
		["_Test Cash", "Cash In Hand", 0, "Cash", None],
		["_Test Account Stock Expenses", "Direct Expenses", 1, None, None],
		["_Test Account Shipping Charges", "_Test Account Stock Expenses", 0, "Chargeable", None],
		["_Test Account Customs Duty", "_Test Account Stock Expenses", 0, "Tax", None],
		["_Test Account Insurance Charges", "_Test Account Stock Expenses", 0, "Chargeable", None],
		["_Test Account Stock Adjustment", "_Test Account Stock Expenses", 0, "Stock Adjustment", None],
		["_Test Employee Advance", "Current Liabilities", 0, None, None],
		["_Test Account Tax Assets", "Current Assets", 1, None, None],
		["_Test Account VAT", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Service Tax", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Reserves and Surplus", "Current Liabilities", 0, None, None],
		["_Test Account Cost for Goods Sold", "Expenses", 0, None, None],
		["_Test Account Excise Duty", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account Education Cess", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account S&H Education Cess", "_Test Account Tax Assets", 0, "Tax", None],
		["_Test Account CST", "Direct Expenses", 0, "Tax", None],
		["_Test Account Discount", "Direct Expenses", 0, None, None],
		["_Test Write Off", "Indirect Expenses", 0, None, None],
		["_Test Exchange Gain/Loss", "Indirect Expenses", 0, None, None],
		["_Test Account Sales", "Direct Income", 0, None, None],
		# related to Account Inventory Integration
		["_Test Account Stock In Hand", "Current Assets", 0, None, None],
		# fixed asset depreciation
		["_Test Fixed Asset", "Current Assets", 0, "Fixed Asset", None],
		["_Test Accumulated Depreciations", "Current Assets", 0, "Accumulated Depreciation", None],
		["_Test Depreciations", "Expenses", 0, None, None],
		["_Test Gain/Loss on Asset Disposal", "Expenses", 0, None, None],
		# Receivable / Payable Account
		["_Test Receivable", "Current Assets", 0, "Receivable", None],
		["_Test Payable", "Current Liabilities", 0, "Payable", None],
		["_Test Down Payment", "Current Assets", 0, "Receivable", None],
		["_Test Bank USD", "Bank Accounts", 0, "Bank", "USD"],
		["_Test Receivable USD", "Current Assets", 0, "Receivable", "USD"],
		["_Test Payable USD", "Current Liabilities", 0, "Payable", "USD"],
		["_Test Down Payment USD", "Current Assets", 0, "Receivable", "USD"],
	]

	test_objects = []

	for company, abbr in [
		["EN16931 Company 1", "ZGF"],
	]:
		test_objects += make_test_objects(
			"Account",
			[
				{
					"doctype": "Account",
					"account_name": account_name,
					"parent_account": parent_account + " - " + abbr,
					"company": company,
					"is_group": is_group,
					"account_type": account_type,
					"account_currency": currency,
				}
				for account_name, parent_account, is_group, account_type, currency in accounts
			],
		)
	return test_objects


def make_test_records():
	# load file with relative path
	path = os.path.join(os.path.dirname(__file__), "test_records.json")
	with open(path, "r") as f:
		test_records = json.load(f)

	for r in test_records:
		if r == "make_accounts":
			make_accounts()
			continue

		try:
			make_test_objects(
				"MISSING DOCTYPE IN JSON", test_records=[r], verbose=None, reset=True, commit=False
			)
		except Exception as e:
			print(e)
			idbg()
			raise


normalize_re = re.compile(r"(>)\s+|\s+(<)", re.MULTILINE)


@unittest.skipUnless(os.environ.get("TEST_ZUGFERD"), "TEST_ZUGFERD environment variable not set")
class TestZugferd(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_test_records()

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.rollback()

	def normalize(self, xml: str) -> str:
		return normalize_re.sub(r"\1\2", xml)

	def assertEqualXml(self, first: Any, second: Any, msg: Any = None) -> None:
		return self.assertEqual(self.normalize(first), self.normalize(second), msg)

	def test_1_context(self):
		xml = TheTestRenderer().render("test_context", {"x": 1, "y": 2})
		self.assertEqualXml(xml, "<x>1</x><y>2</y>")

	def test_1_address(self):
		fmt = TheTestRenderer().make_formatter({})

		addr: "t.Address" = frappe.get_doc("Address", "EN16931 Address 1")  # type: ignore
		addr_info = AddressInfo.FromAddress(addr)
		self.assertEqual(
			addr_info,
			AddressInfo(
				address_line1="123 Teststraße",
				address_line2="Testhaus 1",
				city="Berlin",
				pincode="10115",
				country_code="DE",
			),
		)

		xml = fmt.address(addr_info)
		self.assertEqualXml(
			xml,
			"""
		<ram:PostalTradeAddress>
			<ram:PostcodeCode>10115</ram:PostcodeCode>
			<ram:LineOne>123 Teststraße</ram:LineOne>
			<ram:LineTwo>Testhaus 1</ram:LineTwo>
			<ram:CityName>Berlin</ram:CityName>
			<ram:CountryID>DE</ram:CountryID>
		</ram:PostalTradeAddress>""",
		)

	def test_1_party(self):
		fmt = TheTestRenderer().make_formatter({})
		company: "t.Company" = frappe.get_doc("Company", "EN16931 Company 1")  # type: ignore
		seller = SellerInfo.FromCompany(company)

		xml = fmt.party("ram:SellerTradeParty", seller)
		self.assertEqualXml(
			xml,
			"""
		<ram:SellerTradeParty>
			<ram:ID>EN16931 Company 1</ram:ID>
			<ram:DefinedTradeContact>
				<ram:TelephoneUniversalCommunication>
					<ram:CompleteNumber>+491230000001</ram:CompleteNumber>
				</ram:TelephoneUniversalCommunication>
				<ram:EmailURIUniversalCommunication>
					<ram:URIID>address1@example.com</ram:URIID>
				</ram:EmailURIUniversalCommunication>
			</ram:DefinedTradeContact>
			<ram:PostalTradeAddress>
				<ram:PostcodeCode>10115</ram:PostcodeCode>
				<ram:LineOne>123 Teststraße</ram:LineOne>
				<ram:LineTwo>Testhaus 1</ram:LineTwo>
				<ram:CityName>Berlin</ram:CityName>
				<ram:CountryID>DE</ram:CountryID>
			</ram:PostalTradeAddress>
			<ram:SpecifiedTaxRegistration>
				<ram:ID schemeID="VA">DE000000001</ram:ID>
			</ram:SpecifiedTaxRegistration>
		</ram:SellerTradeParty>""",
		)

	def test_1_contact(self):
		fmt = TheTestRenderer().make_formatter({})
		contact_name = frappe.db.exists("Contact", {"name": "EN16931 Contact 1"})
		xml = fmt.contact(ContactInfo.FromContactName(contact_name))
		self.assertEqualXml(
			xml,
			"""
		<ram:DefinedTradeContact>
			<ram:PersonName>Andrea Test</ram:PersonName>
			<ram:TelephoneUniversalCommunication>
				<ram:CompleteNumber>+491230000002</ram:CompleteNumber>
			</ram:TelephoneUniversalCommunication>
			<ram:EmailURIUniversalCommunication>
				<ram:URIID>contact1@example.com</ram:URIID>
			</ram:EmailURIUniversalCommunication>
		</ram:DefinedTradeContact>""",
		)

	def test_2_sales_invoice(self):
		si: "t.SalesInvoice" = frappe.get_doc(
			"Sales Invoice",
			[
				("customer", "like", "EN16931 Customer Individual 1 (%)"),
			],  # type: ignore
		)

		print(si.as_dict())

		xml = SalesInvoiceRenderer().render(si)
		xml_check_xsd(xml.encode("utf-8"), flavor="autodetect", level="autodetect")

		print(minidom.parseString(xml).toprettyxml())
