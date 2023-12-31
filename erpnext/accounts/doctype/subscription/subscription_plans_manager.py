import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item
from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod
from erpnext.accounts.party import get_default_price_list
from erpnext.stock.get_item_details import get_price_list_rate_for


class SubscriptionPlansManager:
	def __init__(self, subscription):
		self.subscription = subscription

	def set_plans_status(self):
		current_date = (
			self.subscription.current_invoice_start
			or SubscriptionPeriod(self.subscription).get_current_invoice_start()
		)
		for plan in self.subscription.plans:
			previous_status = plan.status
			if getdate(plan.from_date or "1900-01-01") <= getdate(current_date) and getdate(
				plan.to_date or "3000-12-31"
			) >= getdate(current_date):
				plan.status = "Active"
			elif getdate(plan.from_date or "1900-01-01") >= getdate(current_date) and getdate(
				plan.to_date or "3000-12-31"
			) >= getdate(current_date):
				plan.status = "Upcoming"
			else:
				plan.status = "Inactive"

			if previous_status != plan.status:
				frappe.db.set_value("Subscription Plan Detail", plan.name, "status", plan.status)

	def set_plans_rates(self):
		for plan in [x for x in self.subscription.plans if x.status in ("Active", "Upcoming")]:
			previous_rate = plan.rate
			date = getdate(nowdate()) if plan.status == "Active" else getdate(plan.from_date)
			if not plan.uom:
				plan.uom = frappe.get_cached_value("Item", plan.item, "sales_uom") or frappe.get_cached_value(
					"Item", plan.item, "stock_uom"
				)
			plan.rate = self.get_plan_rate(plan, date)

			if flt(previous_rate) != flt(plan.rate):
				frappe.db.set_value("Subscription Plan Detail", plan.name, "rate", plan.rate)

	def get_plans_total(self):
		max_date = (
			add_days(getdate(self.subscription.current_invoice_end), 1)
			if self.subscription.generate_invoice_at_period_start
			else self.subscription.current_invoice_end
		)
		total = 0
		for plan in [x for x in self.subscription.plans if x.status in ("Active", "Upcoming")]:
			if not plan.to_date or getdate(plan.to_date) <= getdate(max_date):
				date = getdate(nowdate()) if plan.status == "Active" else getdate(plan.from_date)
				total += flt(plan.qty) * flt(self.get_plan_rate(plan, date))

		return total

	def get_plan_rate(self, plan, date=nowdate()):
		if plan.price_determination == "Fixed rate":
			return plan.fixed_rate

		elif plan.price_determination == "Based on price list":
			price_list = None
			if hasattr(self.subscription, "customer"):
				customer_doc = frappe.get_doc("Customer", self.subscription.customer)
				price_list = get_default_price_list(customer_doc)
			if not price_list:
				price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")

			args = {
				"company": self.subscription.company,
				"uom": plan.uom,
				"price_list": price_list,
				"currency": self.subscription.currency,
				"transaction_date": date,
				"qty": plan.qty,
			}

			if frappe.db.get_value("Item", plan.item, "stock_uom") != plan.uom:
				item = frappe.get_doc("Item", plan.item)
				conversion_factors = [cf.conversion_factor for cf in item.uoms if cf.uom == plan.uom]
				if conversion_factors:
					args.update({"conversion_factor": conversion_factors[0]})

			if hasattr(self.subscription, "customer"):
				args.update({"customer": self.subscription.customer})

			price_list_rate = get_price_list_rate_for(args, plan.item)

			args.update(
				{
					"item_code": plan.item,
					"stock_qty": plan.qty,
					"transaction_type": "selling",
					"price_list_rate": price_list_rate,
					"price_list_currency": frappe.db.get_value("Price List", price_list, "currency"),
					"transaction_date": date,
					"warehouse": frappe.db.get_value("Warehouse", dict(is_group=1, parent_warehouse="")),
				}
			)
			rule = get_pricing_rule_for_item(frappe._dict(args))

			if rule.get("price_list_rate"):
				price_list_rate = rule.get("price_list_rate")

			return price_list_rate or 0
