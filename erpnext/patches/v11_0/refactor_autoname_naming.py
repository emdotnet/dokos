# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

doctype_series_map = {
	"Activity Cost": "PROJ-ACC-.#####",
	"Asset Movement": "ACC-ASM-.YYYY.-.#####",
	"Attendance Request": "HR-ARQ-.YY.-.MM.-.#####",
	"Authorization Rule": "HR-ARU-.#####",
	"Bank Guarantee": "ACC-BG-.YYYY.-.#####",
	"Bin": "MAT-BIN-.YYYY.-.#####",
	"Chat Room": "CHAT-ROOM-.#####",
	"Compensatory Leave Request": "HR-CMP-.YY.-.MM.-.#####",
	"Client Script": "SYS-SCR-.#####",
	"Employee Benefit Application": "HR-BEN-APP-.YY.-.MM.-.#####",
	"Employee Benefit Application Detail": "",
	"Employee Benefit Claim": "HR-BEN-CLM-.YY.-.MM.-.#####",
	"Employee Incentive": "HR-EINV-.YY.-.MM.-.#####",
	"Employee Onboarding": "HR-EMP-ONB-.YYYY.-.#####",
	"Employee Onboarding Template": "HR-EMP-ONT-.#####",
	"Employee Promotion": "HR-EMP-PRO-.YYYY.-.#####",
	"Employee Separation": "HR-EMP-SEP-.YYYY.-.#####",
	"Employee Separation Template": "HR-EMP-STP-.#####",
	"Employee Tax Exemption Declaration": "HR-TAX-DEC-.YYYY.-.#####",
	"Employee Tax Exemption Proof Submission": "HR-TAX-PRF-.YYYY.-.#####",
	"Employee Transfer": "HR-EMP-TRN-.YYYY.-.#####",
	"Event": "EVENT-.YYYY.-.#####",
	"Exchange Rate Revaluation": "ACC-ERR-.YYYY.-.#####",
	"GL Entry": "ACC-GLE-.YYYY.-.#####",
	"Item Price": "",
	"Job Applicant": "HR-APP-.YYYY.-.#####",
	"Job Offer": "HR-OFF-.YYYY.-.#####",
	"Leave Encashment": "HR-ENC-.YYYY.-.#####",
	"Leave Period": "HR-LPR-.YYYY.-.#####",
	"Leave Policy": "HR-LPOL-.YYYY.-.#####",
	"Loan": "ACC-LOAN-.YYYY.-.#####",
	"Loan Application": "ACC-LOAP-.YYYY.-.#####",
	"Loyalty Point Entry": "",
	"Packing Slip": "MAT-PAC-.YYYY.-.#####",
	"Patient Appointment": "HLC-APP-.YYYY.-.#####",
	"Payment Terms Template Detail": "",
	"Payroll Entry": "HR-PRUN-.YYYY.-.#####",
	"Period Closing Voucher": "ACC-PCV-.YYYY.-.#####",
	"POS Closing Entry": "POS-CLO-.YYYY.-.#####",
	"Prepared Report": "SYS-PREP-.YYYY.-.#####",
	"Quotation Item": "",
	"Retention Bonus": "HR-RTB-.YYYY.-.#####",
	"Sales Taxes and Charges": "",
	"Share Transfer": "ACC-SHT-.YYYY.-.#####",
	"Shift Assignment": "HR-SHA-.YY.-.MM.-.#####",
	"Shift Request": "HR-SHR-.YY.-.MM.-.#####",
	"SMS Log": "SYS-SMS-.#####",
	"Stock Ledger Entry": "MAT-SLE-.YYYY.-.#####",
	"Subscription": "ACC-SUB-.YYYY.-.#####",
	"Task": "TASK-.YYYY.-.#####",
	"Tax Rule": "ACC-TAX-RULE-.YYYY.-.#####",
	"UOM Conversion Factor": "MAT-UOM-CNV-.#####",
	"Workflow Action": "SYS-WACT-.#####",
}


def execute():
	series_to_set = get_series()
	for doctype, opts in series_to_set.items():
		set_series(doctype, opts["value"])


def set_series(doctype, value):
	doc = frappe.db.exists("Property Setter", {"doc_type": doctype, "property": "autoname"})
	if doc:
		frappe.db.set_value("Property Setter", doc, "value", value)
	else:
		make_property_setter(doctype, "", "autoname", value, "", for_doctype=True)


def get_series():
	series_to_set = {}

	for doctype in doctype_series_map:
		if not frappe.db.exists("DocType", doctype):
			continue

		if not frappe.db.a_row_exists(doctype):
			continue

		series_to_preserve = get_series_to_preserve(doctype)
		if not series_to_preserve:
			continue

		# set autoname property setter
		if series_to_preserve:
			series_to_set[doctype] = {"value": series_to_preserve}

	return series_to_set


def get_series_to_preserve(doctype):
	series_to_preserve = frappe.db.get_value("DocType", doctype, "autoname")
	return series_to_preserve
