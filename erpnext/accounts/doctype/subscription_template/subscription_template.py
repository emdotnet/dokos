# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import copy

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.model.document import Document
from frappe.utils import get_first_day, get_last_day, getdate, nowdate

from erpnext.accounts.doctype.tax_rule.tax_rule import get_tax_template
from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod


class SubscriptionTemplate(Document):
	def make_subscription(self, **kwargs):
		"""
		Create a new subscription from subscription template
		:param kwargs: Extra parameters containing at least `company`, `customer` and `start`.
		"""
		kwargs = frappe._dict(kwargs)
		if not kwargs.get("ignore_permissions"):
			kwargs.ignore_permissions = False

		if not (kwargs.company and kwargs.customer):
			frappe.throw(_("Please provide the company and the customer"))

		values = {x: getattr(self, x) for x in self.as_dict() if x not in self.get_excluded_fields()}
		start_date = self.get_start_date(kwargs.start_date)
		cancellation_date = self.get_cancellation_date(start_date)

		# Cast `datetime` objects to `date` objects
		from datetime import datetime, date
		if isinstance(start_date, datetime):
			start_date = start_date.date()
		elif not isinstance(start_date, (date, str)):
			raise ValueError(_("Invalid Date"))

		subscription = frappe.get_doc(
			dict(
				{
					"doctype": "Subscription",
					"subscription_template": self.name,
					"sales_order_item": kwargs.sales_order_item,
					"company": kwargs.company,
					"customer": kwargs.customer,
					"start": start_date,
					"plans": self.get_plans_from_template(),
					"tax_template": self.get_tax_template(start_date, kwargs.customer, kwargs.company),
					"cancellation_date": cancellation_date
				},
				**values
			)
		)

		subscription.insert(ignore_permissions=kwargs.ignore_permissions)
		return subscription

	@staticmethod
	def get_excluded_fields():
		return ["name", "owner", "creation", "modified", "modified_by", "doctype"]

	def get_start_date(self, start=None):
		if not start:
			start = getdate(nowdate())

		if self.start_date == "Creation date":
			return start
		elif self.start_date == "1st day of the month":
			return get_first_day(start)
		elif self.start_date == "15th day of the month":
			return getdate(start).replace(day=1)
		elif self.start_date == "Last day of the month":
			return get_last_day(start)
		

	def get_cancellation_date(self, start_date):
		if self.ends_after_first_period:
			return SubscriptionPeriod(self, start=start_date).get_current_invoice_end()

	def get_plans_from_template(self):
		if self.subscription_plan:
			output = []
			for plan_line in frappe.get_doc(
				"Subscription Plan", self.subscription_plan
			).subscription_plans_template:
				line = copy.deepcopy(plan_line)
				output.append(dict(line.as_dict(), **{"name": None}))
			return output

		else:
			frappe.throw(_("Please select a subscription plan"))

	def get_tax_template(self, start_date, customer, company):
		filters = {"company": company}
		filters.update(
			frappe.db.get_value(
				"Customer", customer, ["name as customer", "customer_group", "tax_category"], as_dict=True
			)
		)
		invoicing_address = get_preferred_address("Customer", customer)
		if invoicing_address:
			filters.update(
				frappe.db.get_value(
					"Address",
					invoicing_address,
					[
						"city as billing_city",
						"county as billing_county",
						"state as billing_state",
						"pincode as billing_zipcode",
						"country as billing_country",
					],
					as_dict=True,
				)
			)

		delivery_address = get_preferred_address("Customer", customer, "is_shipping_address")
		if delivery_address:
			filters.update(
				frappe.db.get_value(
					"Address",
					delivery_address,
					[
						"city as shipping_city",
						"county as shipping_county",
						"state as shipping_state",
						"pincode as shipping_zipcode",
						"country as shipping_country",
					],
					as_dict=True,
				)
			)

		return get_tax_template(start_date, filters)


@frappe.whitelist()
def make_subscription(template, company, customer, start_date, ignore_permissions=False):
	return frappe.get_doc("Subscription Template", template).make_subscription(
		**{
			"company": company,
			"customer": customer,
			"start_date": start_date,
			"ignore_permissions": ignore_permissions,
		}
	)


def make_subscription_from_sales_order_item(doc, method):
	if doc.order_type != "Shopping Cart":
		return

	for item in doc.get("items"):
		subscription_template = frappe.get_cached_value(
			"Item", item.get("item_code"), "subscription_template"
		)
		if subscription_template:
			subscription = frappe.get_doc("Subscription Template", subscription_template).make_subscription(
				**{
					"company": doc.company,
					"customer": doc.customer,
					"sales_order_item": item.name,
					"start_date": item.delivery_date,
					"ignore_permissions": True,
				}
			)

			doc.subscription = subscription.name
			doc.add_subscription_event()
			frappe.db.set_value(doc.doctype, doc.name, "subscription", subscription.name)
