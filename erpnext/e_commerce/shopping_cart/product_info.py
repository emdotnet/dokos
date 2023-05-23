# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint

from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
	show_quantity_in_website,
)
from erpnext.e_commerce.shopping_cart.cart import (
	_get_cart_quotation,
	_set_price_list,
	get_shopping_cart_settings,
)
from erpnext.utilities.product import (
	get_non_stock_item_status,
	get_price,
	get_web_item_qty_in_stock,
)


@frappe.whitelist(allow_guest=True)
def get_product_info_for_website(item_code, skip_quotation_creation=False, enabled_uoms=None):
	"""get product price / stock info for website"""

	if not enabled_uoms:
		enabled_uoms = []

	cart_settings = get_shopping_cart_settings()
	if not cart_settings.enabled:
		# return settings even if cart is disabled
		return frappe._dict({"product_info": {}, "cart_settings": cart_settings})

	cart_quotation = frappe._dict()
	if not skip_quotation_creation:
		cart_quotation = _get_cart_quotation()

	selling_price_list = (
		cart_quotation.get("selling_price_list")
		if cart_quotation
		else _set_price_list(cart_settings, None)
	)

	item_info = frappe.db.get_value(
		"Item", item_code, ("stock_uom", "sales_uom", "enable_item_booking"), as_dict=True
	)

	price = {}
	price_per_uom = {}
	credits_per_uom = {}
	if cart_settings.show_price:
		is_guest = frappe.session.user == "Guest"
		# Show Price if logged in.
		# If not logged in, check if price is hidden for guest.
		if not is_guest or not cart_settings.hide_price_for_guest:
			base_uom = item_info.get("sales_uom") or item_info.get("stock_uom")
			price = get_price(
				item_code,
				selling_price_list,
				cart_settings.default_customer_group,
				cart_settings.company,
				uom=(base_uom),
			)

			if item_info.enable_item_booking:
				credits_per_uom[base_uom] = get_credits_per_item_and_uom(item_code, base_uom)

			for uom in enabled_uoms:
				price_per_uom[uom] = (
					get_price(
						item_code,
						selling_price_list,
						cart_settings.default_customer_group,
						cart_settings.company,
						uom=uom,
					)
					or {}
				)

				if item_info.enable_item_booking:
					credits_per_uom[uom] = get_credits_per_item_and_uom(item_code, uom)

	stock_status = None

	if cart_settings.show_stock_availability:
		on_backorder = frappe.get_cached_value("Website Item", {"item_code": item_code}, "on_backorder")
		if on_backorder:
			stock_status = frappe._dict({"on_backorder": True})
		else:
			stock_status = get_web_item_qty_in_stock(item_code, "website_warehouse")

	product_info = {
		"price": price,
		"qty": 0,
		"uom": item_info.get("stock_uom"),
		"sales_uom": item_info.get("sales_uom") or item_info.get("stock_uom"),
		"price_per_uom": price_per_uom,
		"credits_per_uom": credits_per_uom,
	}

	if stock_status:
		if stock_status.on_backorder:
			product_info["on_backorder"] = True
		else:
			product_info["stock_qty"] = stock_status.stock_qty
			product_info["in_stock"] = (
				stock_status.in_stock
				if stock_status.is_stock_item
				else get_non_stock_item_status(item_code, "website_warehouse")
			)
			product_info["show_stock_qty"] = show_quantity_in_website()

	if product_info["price"]:
		if frappe.session.user != "Guest":
			item = cart_quotation.get({"item_code": item_code}) if cart_quotation else None
			if item:
				product_info["qty"] = item[0].qty

	return frappe._dict({"product_info": product_info, "cart_settings": cart_settings})


def set_product_info_for_website(item):
	"""set product price uom for website"""
	product_info = get_product_info_for_website(item.item_code, skip_quotation_creation=True).get(
		"product_info"
	)

	if product_info:
		item.update(product_info)
		item["stock_uom"] = product_info.get("uom")
		item["sales_uom"] = product_info.get("sales_uom")
		if product_info.get("price"):
			item["price_stock_uom"] = product_info.get("price").get("formatted_price")
			item["price_sales_uom"] = product_info.get("price").get("formatted_price_sales_uom")
		else:
			item["price_stock_uom"] = ""
			item["price_sales_uom"] = ""


def get_credits_per_item_and_uom(item, uom):
	from erpnext.venue.doctype.booking_credit.booking_credit import get_booking_credits_by_item

	if balance := get_booking_credits_by_item(item, uom):
		bct = frappe.qb.DocType("Booking Credit Type")
		bctc = frappe.qb.DocType("Booking Credit Type Conversions")
		result = (
			frappe.qb.from_(bct)
			.inner_join(bctc)
			.on(bct.name == bctc.parent)
			.select(bctc.credits)
			.where(bct.disabled == 0)
			.where(bct.uom == uom)
			.where(bctc.item == item)
		).run(as_dict=True)

		if result and cint(result[0].credits) <= cint(balance):
			return result[0].credits

	return 0.0
