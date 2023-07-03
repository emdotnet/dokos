import re

import frappe

from ..common import types as t
from ..common.data.sinv import SalesInvoiceInfo
from .data import BuyerInfo, SellerInfo
from .formatter import BaseFormatter

# https://ec.europa.eu/taxation_customs/vies/#/faq#Q11


class BaseRenderer:
	@classmethod
	def template_paths(cls):
		return {}

	@classmethod
	def make_formatter(cls, ctx) -> BaseFormatter:
		context = frappe._dict(ctx)
		fmt = BaseFormatter(global_context=context, template_paths=cls.template_paths())
		context["fmt"] = fmt

		return fmt


class TheTestRenderer(BaseRenderer):
	@classmethod
	def template_paths(cls):
		return {
			"test_context": "erpnext/utilities/zugferd/tests/test_context.xml",
		}

	def render(self, template_name: str, globals_=None, locals_=None) -> str:
		fmt = self.make_formatter(globals_ or {})
		return fmt.render(template_name, locals_ or {})


class SalesInvoiceRenderer(BaseRenderer):
	@classmethod
	def template_paths(cls):
		return {
			"base": "erpnext/utilities/zugferd/templates/en16931.xml",
			"item": "erpnext/utilities/zugferd/templates/trade_item.xml",
			"product": "erpnext/utilities/zugferd/templates/trade_product.xml",
			"tax": "erpnext/utilities/zugferd/templates/trade_tax.xml",
			"allowance_charge": "erpnext/utilities/zugferd/templates/trade_allowance_charge.xml",
		}

	def render(self, doc: "t.SalesInvoice") -> str:
		info = SalesInvoiceInfo.FromDoc(doc)
		fmt = self.make_formatter({"doc": doc, "info": info})

		company: "t.Company" = frappe.get_doc("Company", doc.company)  # type: ignore
		fmt.context["seller"] = SellerInfo.FromCompany(company)
		fmt.context["buyer"] = BuyerInfo.FromDoc(doc)

		xml = fmt.render(
			"base", doc.__dict__
		)  # make direct access to doc fields possible only on top level
		# xml = re.compile(r">\s+<").sub(">\n<", xml)
		xml = re.compile(r">\s+<").sub("><", xml)
		return xml
