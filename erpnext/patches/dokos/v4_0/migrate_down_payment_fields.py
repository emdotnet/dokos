import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	frappe.reload_doc("accounts", "doctype", "Company")

	try:
		rename_field(
			"Company", "default_down_payment_receivable_account", "default_advance_received_account"
		)
		rename_field("Company", "default_down_payment_payable_account", "default_advance_paid_account")

	except Exception as e:
		if e.args[0] != 1054:
			raise
