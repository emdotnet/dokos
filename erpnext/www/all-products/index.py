import frappe
from frappe.utils import cint

from erpnext.e_commerce.product_data_engine.filters import ProductFiltersBuilder
from erpnext.e_commerce.shopping_cart.cart import get_shopping_cart_settings

sitemap = 1


def get_context(context):
	# Add homepage as parent
	context.body_class = "product-page"
	context.parents = [{"name": frappe._("Home"), "route": "/"}]

	filter_engine = ProductFiltersBuilder()
	context.field_filters = filter_engine.get_field_filters()
	context.attribute_filters = filter_engine.get_attribute_filters()

	context.page_length = (
		cint(get_shopping_cart_settings().products_per_page) or 20
	)

	context.no_cache = 1
