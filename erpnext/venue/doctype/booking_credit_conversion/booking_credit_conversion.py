# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class BookingCreditConversion(Document):
	def onload(self):
		self.set_onload('all_items', frappe.get_all("Item", filters={"enable_item_booking": 1}, fields=["item_code", "item_name"]))

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_convertible_items(doctype, txt, searchfield, start, page_len, filters):
	query_filters={}
	if txt:
		query_filters={"booking_credits_item", ("like", txt)}
	return [frappe.get_all("Booking Credit Conversion", filters=query_filters, pluck="booking_credits_item")]