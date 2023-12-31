# Copyright (c) 2023, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime

from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
	get_shopping_cart_settings,
)
from erpnext.e_commerce.product_data_engine.query import ProductQuery
from erpnext.venue.doctype.item_booking.item_booking import get_availabilities


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True
	context.full_width = True

	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)


@frappe.whitelist()
def get_item_groups():
	return frappe.get_all(
		"Website Item", filters={"enable_item_booking": 1}, distinct=True, pluck="item_group"
	)


@frappe.whitelist()
def count_item_groups():
	# Perform query to get items
	engine = ProductQuery()
	engine.page_length = 999999999
	engine.filters = [["enable_item_booking", "=", 1]]
	result = engine.query(fields={})
	items = result["items"]

	# Count available/total items per group
	counts = {}
	for item in items:
		group = item.item_group
		if group not in counts:
			counts[group] = 0
		counts[group] += 1

	groups = []
	for group_name in counts:
		group_count = counts[group_name]
		if group_count:
			groups.append(
				{
					"label": frappe._(group_name),
					"value": group_name,
					"count": group_count,
				}
			)

	return groups


@frappe.whitelist()
def get_items(filters=None):
	if filters:
		filters = frappe.parse_json(filters)

	query_filters = [
		["enable_item_booking", "=", 1],
	]
	if filters.get("item_groups"):
		query_filters.append(["item_group", "in", filters.get("item_groups")])

	search_term = filters.get("search", "")

	# Perform query to get items
	engine = ProductQuery()
	engine.page_length = 999999999
	engine.filters = query_filters
	result = engine.query(fields={}, search_term=search_term, start=0, item_group=None)
	items = result["items"]

	# Get availabilities for each item
	start_date, end_date = filters.get("start_date"), filters.get("end_date")
	if start_date and end_date:
		start_date, end_date = getdate(start_date), getdate(end_date)
		end_date = add_days(end_date, 1)
		for item in items:
			try:
				item.availabilities = get_availabilities(item.item_code, start_date, end_date)
			except frappe.ValidationError:
				frappe.clear_last_message()
				item.availabilities = []

	# Count available/total items per group
	group_counts = {}
	for item in items:
		group = item.item_group
		if group not in group_counts:
			group_counts[group] = {"total": 0, "available": 0}

		group_counts[group]["total"] += 1
		if item.availabilities:
			group_counts[group]["available"] += 1

	# Sort by availability, then by name
	items.sort(key=lambda item: (bool(item.availabilities), item.item_name))

	return {"items": items, "group_counts": group_counts, "settings": get_shopping_cart_settings()}


@frappe.whitelist()
def get_upcoming_bookings():
	user = frappe.session.user

	bookings = frappe.get_all(
		"Item Booking",
		filters={
			"user": user,
			"starts_on": (">", now_datetime()),
			"status": ("in", ("Confirmed", "Not Confirmed")),
		},
		fields=["item_name", "user", "starts_on", "ends_on"],
	)

	output = defaultdict(list)
	for booking in bookings:
		output[booking.item_name].append(booking)

	return output
