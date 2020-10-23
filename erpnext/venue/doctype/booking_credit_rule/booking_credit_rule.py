# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import calendar
import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import time_diff_in_minutes, nowdate, getdate, now_datetime, add_to_date, get_datetime, time_diff, get_time, flt
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes, get_item_calendar
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.doctype.booking_credit.booking_credit import get_balance
from erpnext.controllers.website_list_for_contact import get_customers_suppliers

ACTION_MAP = {
	"after_insert": "After Insert",
	"on_update": "If Status Changes",
	"on_submit": "On Submit",
	"on_cancel": "On Cancel",
	"on_trash": "On Delete"
}

class BookingCreditRule(Document):
	def process_rule(self, doc):
		if self.trigger_action == "If Status Changes" and doc.status != self.expected_status:
			return

		return RuleProcessor(self, doc).process()

	def process_timely_rule(self):
		used_docs = frappe.get_all("Booking Credit Usage Reference",
			filters={"reference_doctype": self.trigger_document},
			fields=["reference_document"],
			pluck="reference_document"
		)

		if self.trigger_action == "After Document Start Time":
			time_field = self.start_time_field
		else:
			time_field = self.end_time_field

		filters = {
			time_field: ("<=", now_datetime()),
			"name": ("not in", used_docs),
			"creation": (">", self.creation)
		}

		docs = frappe.get_all(self.trigger_document, filters=filters)

		for doc in docs:
			self.process_rule(doc)

def trigger_credit_rules(doc, method):
	if (frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard):
		return

	rules = frappe.get_all("Booking Credit Rule", 
		filters={
			"disabled": 0,
			"trigger_document": doc.doctype,
			"trigger_action": ACTION_MAP.get(method)
		})
	for rule in rules:
		frappe.get_doc("Booking Credit Rule", rule.name).process_rule(doc)

def trigger_after_specific_time():
	rules = frappe.get_all("Booking Credit Rule", 
		filters={
			"disabled": 0,
			"trigger_action": ("in", ("After Document Start Datetime", "After Document End Datetime"))
		}, fields=["name"])

	for rule in rules:
		frappe.get_doc("Booking Credit Rule", rule.name).process_timely_rule()


@frappe.whitelist()
def get_fieldtypes_options(doctype, fieldtypes):
	try:
		fieldtypes = frappe.parse_json(fieldtypes)
	except Exception:
		fieldtypes = (fieldtypes)

	result = frappe.get_all("DocField",
		filters={
			"parent": doctype,
			"fieldtype": ("in", fieldtypes)
		},
		fields=["fieldname as value", "label"])

	return [{"value": _(x.value), "label": _(x.label)} for x in result]

@frappe.whitelist()
def get_status_options(doctype):
	options = frappe.get_all("DocField",
		filters={
			"parent": doctype,
			"fieldname": "status"
		},
		fields=["options"],
		pluck="options")

	return options[0].split("\n") if options else ""

@frappe.whitelist()
def get_link_options(doctype, link):
	result = frappe.get_all("DocField",
		filters={
			"parent": doctype,
			"fieldtype": "Link",
			"options": link
		},
		fields=["fieldname as value", "label"]) + frappe.get_all("DocField",
			filters={
				"parent": doctype,
				"fieldtype": "Dynamic Link"
			},
			fields=["fieldname as value", "label"])

	return [{"value": _(x.value), "label": _(x.label)} for x in result]

@frappe.whitelist()
def get_child_tables(doctype):
	return [
		{
			"value": x.fieldname,
			"label": _(x.label)
		} for x in frappe.get_meta(doctype).fields if x.fieldtype == "Table"
	]

class RuleProcessor:
	def __init__(self, rule, doc):
		self.rule = rule
		self.doc = doc
		self.user = getattr(doc, self.rule.user_field, None) if self.rule.user_field else None
		self.customer = getattr(doc, self.rule.customer_field, None) if self.rule.customer_field else None
		self.uom = self.qty = self.item = None
		self.start = get_datetime(getattr(doc, self.rule.start_time_field, now_datetime())) if self.rule.start_time_field else now_datetime()
		self.end = get_datetime(getattr(doc, self.rule.end_time_field, now_datetime())) if self.rule.end_time_field else now_datetime()
		self.datetime = now_datetime()
		self.duration = time_diff_in_minutes(self.end, self.start) or 1
		self.min_time = None

	def process(self):
		if not self.customer:
			if not self.user:
				return

			customers, dummy = get_customers_suppliers("Customer", self.user)
			if customers:
				self.customer = customers[0]

		if not (self.customer or self.user):
			return

		if self.rule.rule_type == "Booking Credits Deduction":
			self.datetime = get_datetime(self.start)
			self.item = getattr(self.doc, self.rule.item_field, None) if self.rule.item_field else None

			if self.rule.applicable_for and self.check_application_rule(self.doc):
				return

			if self.rule.custom_deduction_rule:
				self.apply_custom_rules()
			else:
				self.apply_standard_rules()

		else:
			self.apply_addition_rules()

	def check_application_rule(self, doc):
		meta = frappe.get_meta(doc.doctype)
		if self.rule.applicable_for not in [x.options for x in meta.fields]:
			return True

		fields = [x.fieldname for x in meta.fields if x.options == self.rule.applicable_for]

		for field in fields:
			if getattr(doc, field, None) == self.rule.applicable_for_document_type:
				return False

		return True

	def apply_addition_rules(self):
		self.datetime = getattr(self.doc, self.rule.date_field, None) if self.rule.date_field else now_datetime()
		if self.rule.use_child_table:
			for row in self.doc.get(self.rule.child_table) or []:
				if self.rule.applicable_for and self.check_application_rule(row):
					continue

				self.item = getattr(row, self.rule.item_field, None) if self.rule.item_field else None
				self.uom = getattr(row, self.rule.uom_field, None) if self.rule.uom_field else None
				self.qty = getattr(row, self.rule.qty_field, None) if self.rule.qty_field else None

				if self.uom and self.qty:
					self.add_credit()
		else:
			self.item = getattr(self.doc, self.rule.item_field, None) if self.rule.item_field else None
			self.uom = getattr(self.doc, self.rule.uom_field, None) if self.rule.uom_field else None
			self.qty = getattr(self.doc, self.rule.qty_field, None) if self.rule.qty_field else None

			if self.rule.applicable_for and self.check_application_rule(self.doc):
				return

			if self.uom and self.qty:
				self.add_credit()

	def apply_standard_rules(self):
		default_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
		customer_balance = get_balance(self.customer, getdate(self.datetime))
		customer_uoms = self.get_ordered_uoms(customer_balance)

		if not self.rule.fifo_deduction and self.start.date() == self.end.date():
			for uom in customer_uoms:
				booking_calendar = get_item_calendar(self.item, uom)
				if booking_calendar:
					daily_slots = [x for x in booking_calendar.get("calendar") if x.day==calendar.day_name[self.start.date().weekday()]]
					self.min_time = min([x.start_time for x in daily_slots])

					for slot in daily_slots:
						if self.start.time() >= get_time(slot.start_time) and self.end.time() <= get_time(slot.end_time):
							self.uom = uom
							self.qty = self.duration / (get_uom_in_minutes(self.uom) or 1.0)
							break

				if self.uom and self.qty:
					break

		customer_uom = getattr(self.doc, self.rule.uom_field, None) if self.rule.uom_field else None or (customer_uoms[0] if customer_uoms else None)
		self.uom = self.uom or customer_uom or default_uom
		self.qty = self.qty or self.duration / (get_uom_in_minutes(customer_uom or default_uom) or 1.0)

		if self.rule.round_up or self.rule.round_down:
			func = math.ceil if self.rule.round_up else math.floor
			self.qty = func(self.qty)

		if not frappe.db.exists("Booking Credit Usage Reference",
			{"reference_doctype": self.doc.doctype, "reference_document": self.doc.name}) and self.deduction_is_not_already_registered():
			return self.deduct_credit()

	def apply_custom_rules(self):
		import numpy as np
		intervals = [(x.from_duration, x.to_duration) for x in self.rule.booking_credit_rules if x.duration_interval]
		intervals.sort(key=lambda t: t[0])

		levels = [x for x in self.rule.booking_credit_rules if not x.duration_interval]
		min_level = min([x.duration for x in self.rule.booking_credit_rules if not x.duration_interval])

		corresponding_interval = None
		for index, interval in enumerate(intervals):
			if self.duration < interval[0]:
				corresponding_interval = (index - 1) if (index - 1) >= 0 else None

			elif self.duration in range(interval[0], interval[1] + 1) or self.duration > interval[1]:
				corresponding_interval = index

		result = []
		total_duration = self.duration
		if corresponding_interval is not None:
			selected_rule = [x for x in self.rule.booking_credit_rules if x.from_duration == intervals[corresponding_interval][0] and x.to_duration == intervals[corresponding_interval][1]][0]
			total_duration -= min(flt(total_duration), flt(selected_rule.to_duration))
			result.append((selected_rule.credit_qty, selected_rule.credit_uom))

		while total_duration > 0:
			if self.rule.round_down and total_duration < min_level:
				break

			closest_index = np.argmin(np.abs(np.array([x.duration for x in levels]) - total_duration))
			total_duration -= min(flt(levels[closest_index].duration), flt(total_duration))
			result.append((levels[closest_index].credit_qty, levels[closest_index].credit_uom))

		for index, res in enumerate(result):
			self.qty = res[0]
			self.uom = res[1]

			self.deduct_credit()

	def add_credit(self):
		doc = frappe.get_doc({
			"doctype": "Booking Credit",
			"date": getdate(self.datetime),
			"customer": self.customer,
			"quantity": self.qty,
			"uom": self.uom
		}).insert(ignore_permissions=True)
		return doc.submit()

	def deduct_credit(self):
		usage = frappe.get_doc({
			"doctype": "Booking Credit Usage",
			"datetime": self.datetime,
			"customer": self.customer,
			"quantity": self.qty,
			"uom": self.uom,
		}).insert(ignore_permissions=True)

		self.insert_deduction_reference(usage.name)

		return usage.submit()

	def insert_deduction_reference(self, usage):
		frappe.get_doc({
			"doctype": "Booking Credit Usage Reference",
			"booking_credit_usage": usage,
			"reference_doctype": self.doc.doctype,
			"reference_document": self.doc.name
		}).insert(ignore_permissions=True)

	def deduction_is_not_already_registered(self):
		if self.uom == frappe.db.get_single_value("Venue Settings", "month_uom"):
			start_time = get_first_day(getdate(self.start))
			end_time = get_last_day(getdate(self.end))
		else:
			uom_minutes = get_uom_in_minutes(self.uom)
			start_time = min(add_to_date(get_datetime(self.end), minutes=(uom_minutes * -1)), get_datetime(self.start))
			if self.min_time and get_time(self.min_time) >= add_to_date(get_datetime(self.start), minutes=(uom_minutes * -1)).time():
				start_time = get_datetime(self.start).replace(hour=get_time(self.min_time).hour, minute=get_time(self.min_time).minute)

			end_time = add_to_date(start_time, minutes=(uom_minutes))

		usages = frappe.db.sql(f"""SELECT name FROM `tabBooking Credit Usage`
			WHERE datetime > '{start_time}'
			AND datetime < '{end_time}'
			AND coalesce(customer, "") = {frappe.db.escape(self.customer)}
			AND coalesce(user, "") = {frappe.db.escape(self.user)}
		""", debug=True)

		for usage in usages:
			self.insert_deduction_reference(usage[0])

		if usages:
			return False

		return True


	def get_ordered_uoms(self, balance):
		if self.rule.fifo_deduction:
			return [x["uom"] for x in sorted(balance, key = lambda i: i['date'])]
		else:
			uoms = [x["uom"] for x in customer_balance]
			return frappe.get_all("UOM Conversion Factor",
				filters={
					"from_uom": ("in", uoms),
					"to_uom": frappe.db.get_single_value("Venue Settings", "minute_uom")
				},
				fields=["from_uom"],
				order_by="value ASC",
				pluck="from_uom"
			)
