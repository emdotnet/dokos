# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import (
	unlink_payment_on_cancel_of_invoice,
)
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	create_dunning as create_dunning_from_sales_invoice,
)
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import (
	create_sales_invoice_against_cost_center,
)


class TestDunning(FrappeTestCase):
	@classmethod
	def setUpClass(self):
		create_dunning_type("First Notice", fee=0.0, interest=0.0, is_default=1)
		create_dunning_type("Second Notice", fee=10.0, interest=10.0, is_default=0)
		unlink_payment_on_cancel_of_invoice()

	@classmethod
	def tearDownClass(self):
		unlink_payment_on_cancel_of_invoice(0)

	def test_first_dunning(self):
		dunning = create_dunning(overdue_days=20)

		self.assertEqual(round(dunning.total_outstanding, 2), 100.00)
		self.assertEqual(round(dunning.total_interest, 2), 0.00)
		self.assertEqual(round(dunning.dunning_fee, 2), 0.00)
		self.assertEqual(round(dunning.dunning_amount, 2), 0.00)
		self.assertEqual(round(dunning.grand_total, 2), 100.00)

	def test_second_dunning(self):
		dunning = create_dunning(overdue_days=15, dunning_type_name="Second Notice")

		self.assertEqual(round(dunning.total_outstanding, 2), 100.00)
		self.assertEqual(round(dunning.total_interest, 2), 0.41)
		self.assertEqual(round(dunning.dunning_fee, 2), 10.00)
		self.assertEqual(round(dunning.dunning_amount, 2), 10.41)
		self.assertEqual(round(dunning.grand_total, 2), 110.41)

	def test_payment_entry(self):
		dunning = create_dunning(overdue_days=15, dunning_type_name="Second Notice")
		dunning.submit()
		pe = get_payment_entry("Dunning", dunning.name)
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.insert()
		pe.submit()

		for overdue_payment in dunning.overdue_payments:
			outstanding_amount = frappe.get_value(
				"Sales Invoice", overdue_payment.sales_invoice, "outstanding_amount"
			)
			self.assertEqual(outstanding_amount, 0)

		dunning.reload()
		self.assertEqual(dunning.status, "Resolved")


def create_dunning(overdue_days, dunning_type_name=None):
	posting_date = add_days(today(), -1 * overdue_days)
	sales_invoice = create_sales_invoice_against_cost_center(
		posting_date=posting_date, qty=1, rate=100
	)
	dunning = create_dunning_from_sales_invoice(sales_invoice.name)

	if dunning_type_name:
		dunning_type = frappe.get_doc("Dunning Type", dunning_type_name)
		dunning.dunning_type = dunning_type.name
		dunning.rate_of_interest = dunning_type.rate_of_interest
		dunning.dunning_fee = dunning_type.dunning_fee

	dunning.income_account = get_income_account(dunning.company)
	dunning.save()

	return dunning


def create_dunning_type(title, fee, interest, is_default):
	existing = frappe.db.exists("Dunning Type", title)
	if existing:
		return frappe.get_doc("Dunning Type", existing)

	dunning_type = frappe.new_doc("Dunning Type")
	dunning_type.dunning_type = title
	dunning_type.is_default = is_default
	dunning_type.dunning_fee = fee
	dunning_type.rate_of_interest = interest
	dunning_type.append(
		"dunning_letter_text",
		{
			"language": "en",
			"body_text": "We have still not received payment for our invoice",
			"closing_text": "We kindly request that you pay the outstanding amount immediately, including interest and late fees.",
		},
	)
	dunning_type.save()
	return dunning_type


def get_income_account(company):
	return frappe.get_value("Company", company, "default_income_account") or frappe.get_all(
		"Account",
		filters={"is_group": 0, "company": company},
		or_filters={
			"report_type": "Profit and Loss",
			"account_type": ("in", ("Income Account", "Temporary")),
		},
		limit=1,
		pluck="name",
	)[0]
