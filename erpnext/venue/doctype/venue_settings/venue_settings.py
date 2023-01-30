# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

from urllib.parse import unquote
import datetime

from erpnext.venue.doctype.venue_settings.setup_custom_fields import (
	multicompany_create_custom_fields,
	multicompany_delete_custom_fields,
)

class VenueSettings(Document):
	# Support for multiple companies/venues with distinct items
	def onload(self):
		# see: e_commerce_settings.py
		self.get("__onload").quotation_series = frappe.get_meta("Quotation").get_options("naming_series")

	## Hooks
	def validate(self):
		# check that all selected companies are unique in the cart_settings_overrides,
		# even if disabled to avoid mistakes
		unique_companies = set()
		for override in self.cart_settings_overrides:
			if override.company in unique_companies:
				frappe.throw(frappe._('Company {0} is used more than once in the cart settings overrides').format(override.company))
			unique_companies.add(override.company)

		if self.enable_multi_companies and not unique_companies:
			frappe.throw(frappe._('You must select at least one company in the cart settings overrides'))

	def on_update(self):
		old_doc = self.get_doc_before_save()
		did_change = False
		if old_doc:
			did_change = old_doc.enable_multi_companies != self.enable_multi_companies
		else:
			did_change = True
		if did_change:
			if self.enable_multi_companies:
				multicompany_create_custom_fields(self)
			else:
				multicompany_delete_custom_fields(self)

	## Type hints for fields
	enable_multi_companies: bool
	cart_settings_overrides: dict

	## Helpers
	def multicompany_is_company_allowed(self, company):
		if not self.enable_multi_companies:
			return True  # all companies are allowed if the feature is disabled

		for override in self.cart_settings_overrides:
			if override.company == company:
				# return override.enabled
				return True

		return False

	def multicompany_get_allowed_companies(self) -> list:
		return [override.company for override in self.cart_settings_overrides]

	def multicompany_get_current_company(self):
		if self.enable_multi_companies:
			if company := multicompany_read_cookie():
				if self.multicompany_is_company_allowed(company):
					return company

	def multicompany_get_item_filter(self):
		NOT_ALLOWED = ["Venue Selected Company", "company", "=", ""]
		if self.enable_multi_companies:
			if company := self.multicompany_get_current_company():
				return ["Venue Selected Company", "company", "=", company]
			return NOT_ALLOWED
		return None

	def multicompany_get_item_filter_for_company(self, for_company=None):
		NOT_ALLOWED = ["Venue Selected Company", "company", "=", ""]
		if self.enable_multi_companies:
			if self.multicompany_is_company_allowed(for_company):
				return ["Venue Selected Company", "company", "=", for_company]
			return NOT_ALLOWED
		return None


MULTICOMPANY_COOKIE_NAME = "company"
MULTICOMPANY_FLAG_NAME = "multicompany_current_company"
MULTICOMPANY_CONTEXT_ALL_COMPANIES = "multicompany_list"
MULTICOMPANY_CONTEXT_CURRENT_COMPANY = "multicompany_current"

def multicompany_read_cookie():
	return multicompany_read_and_update_cookie()

def multicompany_read_and_update_cookie():
	cached = frappe.flags.get(MULTICOMPANY_FLAG_NAME, 0)
	if cached != 0:
		return cached

	venue_settings: VenueSettings = frappe.get_cached_doc("Venue Settings")

	if not venue_settings.enable_multi_companies:
		multicompany_clear_cookie()  # clear the cookie + set cache
		return None

	# Read the selected company from the query string parameters
	# to overwrite the cookie "company" (MULTICOMPANY_COOKIE_NAME)
	# if valid.
	from_query = frappe.form_dict.get("selected_company", None)
	if from_query:
		is_valid = venue_settings.multicompany_is_company_allowed(from_query)
		if is_valid:
			multicompany_write_cookie(from_query)  # overwrite the cookie
			return from_query
		else:
			frappe.local.flags.redirect_location = "/"
			raise frappe.Redirect
	elif from_query == "":
		# front-end wants to clear of the cookie
		multicompany_clear_cookie()  # clear the cookie + set cache
		return None

	try:
		from_cookie = frappe.request.cookies.get(MULTICOMPANY_COOKIE_NAME, None)
		from_cookie = unquote(from_cookie) if from_cookie else None
		if venue_settings.multicompany_is_company_allowed(from_cookie):
			multicompany_write_cookie(from_cookie)  # refresh the cookie
			return from_cookie
	except RuntimeError:
		# frappe.request is not available in some contexts
		multicompany_clear_cookie()  # clear the cookie
		return None

	multicompany_clear_cookie()  # fallback: clear the cookie
	return None


def multicompany_write_cookie(value):
	frappe.flags[MULTICOMPANY_FLAG_NAME] = value
	if hasattr(frappe.local, "cookie_manager"):
		expires = datetime.datetime.now() + datetime.timedelta(days=14)
		frappe.local.cookie_manager.set_cookie(MULTICOMPANY_COOKIE_NAME, value, expires=expires)


def multicompany_clear_cookie():
	frappe.flags[MULTICOMPANY_FLAG_NAME] = None
	if hasattr(frappe.local, "cookie_manager"):
		frappe.local.cookie_manager.delete_cookie(MULTICOMPANY_COOKIE_NAME)


def update_website_context(context):
	if not frappe.db.get_single_value("Venue Settings", "enable_multi_companies"):
		return

	venue_settings: VenueSettings = frappe.get_cached_doc("Venue Settings")

	if not venue_settings.enable_multi_companies:
		return

	# Get the company from the cookie, which is likely a valid company (or None)
	company = venue_settings.multicompany_get_current_company()  # str | None

	# Update context to include the list of all the allowed companies,
	context[MULTICOMPANY_CONTEXT_CURRENT_COMPANY] = company
	context[MULTICOMPANY_CONTEXT_ALL_COMPANIES] = [
		{ "label": name, "value": name, "selected": name == company }
		for name in venue_settings.multicompany_get_allowed_companies()
	]

	if context["top_bar_items"]:
		# Filter out top bar items that route to excluded item groups

		# If the cookie is invalid, then `company` will be None
		# which means that the JOIN will happen on VSC.company == None,
		# which is always false (as VSC.company is a mandatory field),
		# so all item group routes will be excluded in the end (correct behavior).

		ItemGroup = frappe.qb.DocType('Item Group')
		VSC = frappe.qb.DocType('Venue Selected Company')
		query = frappe.qb.from_(ItemGroup)\
			.select(
				ItemGroup.route,
				VSC.company.isnotnull().as_('allowed')
			).left_join(VSC).on(
				# basic join on child table
				(VSC.parenttype == 'Item Group') & (VSC.parent == ItemGroup.name)
				# additional join condition:
				# if the company matches, include the row, else the row/company NULL (important!)
				& (VSC.company == company)
			).where(ItemGroup.show_in_website == 1)

		excluded_routes = set()
		for res in query.run(as_dict=True):
			# assert res["route"], "Expected `route` to be non-empty, in results of query in e_commerce.shopping_cart.utils.update_website_context"
			if not res["allowed"] and res["route"]:  # note: avoid to exclude "/" by mistake
				route = res["route"]
				if not route.startswith("/"):
					route = "/" + route  # normalize
				excluded_routes.add(route)

		fixed_top_bar_items = []
		for item in context["top_bar_items"]:
			url = item.url or ""
			if not url.startswith("/"):
				url = "/" + url  # normalize
			if url in excluded_routes:
				continue
			fixed_top_bar_items.append(item)
		context["top_bar_items"] = fixed_top_bar_items


def override_e_commerce_settings(e_commerce_settings):
	"""
	Hook that returns a new E Commerce Settings-like object with overrides for
	the current company (stored in cookies) when the multicompany feature is enabled.
	"""
	return get_shopping_cart_overrides()  # NOTE: might return None, which means no override

def get_shopping_cart_overrides(company=None):
	if not hasattr(frappe, "request"):
		raise RuntimeError("override_e_commerce_settings: This function must be called from a `request` context.")

	venue_settings = frappe.get_cached_doc("Venue Settings")
	if not venue_settings.get("enable_multi_companies"):
		return  # multi-company support is disabled

	company = company or venue_settings.multicompany_get_current_company()
	if not company:
		return  # outside of a valid multi-company context

	# everything is ok, return the overrides (if any, and cached)
	return _get_shopping_cart_overrides_cached(company)

from functools import lru_cache
@lru_cache(maxsize=32, typed=True)  # note: there is no way to invalidate this cache if the settings change during runtime
def _get_shopping_cart_overrides_cached(company):
	assert company, "invalid arguments: do not use this function directly"
	venue_settings = frappe.get_cached_doc("Venue Settings")
	cart_settings = frappe.get_cached_doc("E Commerce Settings")

	# find the overrides for the company
	overrides = None
	for o in venue_settings.get("cart_settings_overrides", []):
		if o.get("company") == company:
			overrides = o
			break
	if not overrides: return  # note: could've been a for-else, but this is more readable

	# get and copy the cart_settings to a dict
	cart_settings = cart_settings.as_dict()

	# update the base with the overrides
	# fields = {"company", "price_list", "default_customer_group", "quotation_series"}
	fields = { df.fieldname for df in frappe.get_meta("Venue Cart Settings").get("fields") }
	for fieldname in fields:
		if value := overrides.get(fieldname):
			cart_settings["_" + fieldname + "__original"] = cart_settings[fieldname]
			cart_settings[fieldname] = value

	cart_settings["_was_overridden_by_multicompany_mode"] = True
	cart_settings = frappe._dict(cart_settings)  # convert back to frappe._dict
	return cart_settings
