from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import frappe
from frappe.utils.data import flt

from ..heuristic import (
	get_charge_reason,
	tax_row_is_charge_wise,
	tax_row_is_item_wise,
	tax_row_is_other_charge,
	tax_row_is_vat,
)
from .charge import AllowanceInfo, ChargeInfo
from .item import ItemInfo
from .price import PriceCalcRounded
from .tax import TaxInfo

if TYPE_CHECKING:
	from .. import types as t


@dataclass
class SalesInvoiceInfo:
	currency: str
	precision: int = 2

	_gross_total: float = 0.0
	_net_total: float = 0.0

	doc: "t.SalesInvoice | None" = None
	items: list[ItemInfo] = field(default_factory=list)
	taxes: list[TaxInfo] = field(default_factory=list)
	charges: list[ChargeInfo] = field(default_factory=list)
	allowances: list[AllowanceInfo] = field(default_factory=list)

	document_wise_vat: TaxInfo | None = None

	subtotals: dict[str, float] = field(default_factory=dict)

	@classmethod
	def FromDoc(cls, sinv: "t.SalesInvoice | frappe.Document"):
		info = SalesInvoiceInfo(currency=sinv.currency, doc=sinv)  # type: ignore

		for row in sinv.get("items") or []:
			tax_rate = (row.tax_rate or 0.0) / 100.0
			item_info = ItemInfo.FromSalesInvoiceItemRow(sinv, row, tax_rate)
			info.items.append(item_info)

		object_by_idx: dict[int, TaxInfo | ChargeInfo] = {}

		for idx, tax_row in enumerate(sinv.taxes, start=1):  # type: ignore
			# 'charge_type': 'On Net Total'
			# 'row_id': None,
			# 'account_head': '445720 - TVA 10% - DKY',
			# 'description': 'TVA 10%',
			# 'included_in_print_rate': 0,
			# 'included_in_paid_amount': 0,
			# 'cost_center': 'Principal - DKY',
			# 'rate': 0.0,
			# 'account_currency': 'EUR',
			# 'tax_amount': 19.83,
			# 'total': 614.83,
			# 'tax_amount_after_discount_amount': 19.83,
			# 'base_tax_amount': 19.83,
			# 'base_total': 614.83,
			# 'base_tax_amount_after_discount_amount': 19.83,
			# 'dont_recompute_tax': 0,

			is_item_wise = tax_row_is_item_wise(tax_row)
			is_charge_wise = tax_row_is_charge_wise(tax_row)
			is_document_wise = not is_item_wise and not is_charge_wise

			is_vat = tax_row_is_vat(tax_row)
			is_other_charge = tax_row_is_other_charge(tax_row)
			if is_vat == is_other_charge:
				raise NotImplementedError(
					f"Please contact the service provider. ProgrammingError: Tax row {tax_row!r} is neither/both VAT and other charge"
				)

			tax_rate: float | None = None
			if is_vat:
				if (is_item_wise or is_charge_wise) and tax_row.rate == 0.0:
					tax_rate = frappe.get_value("Account", tax_row.account_head, "tax_rate")
				else:
					tax_rate = tax_row.rate

			if is_item_wise and is_charge_wise:
				raise ValueError(f"Tax row {tax_row!r} is both item-wise and charge-wise")
			if is_vat and is_other_charge:
				raise ValueError(f"Tax row {tax_row!r} is both VAT and other charge")

			# description = " ".join(
			# 	filter(
			# 		None,
			# 		[
			# 			"item-wise" if is_item_wise else None,
			# 			"charge-wise" if is_charge_wise else None,
			# 			"VAT" if is_vat else None,
			# 			"other charge" if is_other_charge else None,
			# 		],
			# 	)
			# )

			tax_info: TaxInfo | None = None
			charge_info: ChargeInfo | None = None

			if is_vat:
				# Base Amount is only correct for document-wise VAT
				base_amount = tax_row.base_tax_amount if is_document_wise else None

				tax_info = TaxInfo(
					amount=tax_row.tax_amount,
					basis=base_amount,
					percent=(tax_rate or 0.0) / 100.0,
					tax_type="VAT",
					category="S",
					currency=sinv.currency,
				)
			elif is_other_charge:
				ch: tuple[str, str] | None = get_charge_reason(tax_row)
				reason, reason_code = ch or (None, None)

				if not reason:
					reason = tax_row.description

				charge_info = ChargeInfo(
					amount=tax_row.tax_amount,
					taxes=[],
					basis=None,
					percent=((tax_row.rate or 0.0) / 100.0) or None,
					reason=reason,
					reason_code=reason_code,
				)
			else:  # other tax
				tax_info = TaxInfo(
					amount=tax_row.tax_amount,
					basis=tax_row.base_tax_amount,
					percent=(tax_rate or 0.0) / 100.0,
					tax_type="?",
					category="S",
					currency=sinv.currency,
				)

			object_by_idx[idx] = tax_info or charge_info  # type: ignore

			if isinstance(tax_row.row_id, (int, str)):
				ref_idx = int(tax_row.row_id)
			elif tax_row.row_id is None:
				ref_idx = None
			else:
				raise ValueError(
					f"Tax row {tax_row.as_dict()!r} has invalid row_id (expected int | None, got {tax_row.row_id!r})"
				)

			if is_document_wise:
				if tax_info:
					if is_vat:
						if info.document_wise_vat is not None:
							raise ValueError(
								f"Tax row {tax_row.as_dict()!r} is document-wise VAT but there is already a document-wise VAT row"
							)
						info.document_wise_vat = tax_info
					else:
						info.taxes.append(tax_info)

				if charge_info:
					info.charges.append(charge_info)

			elif is_item_wise:
				if tax_info:
					pass  # info.item_wise_taxes.append(tax_info)
				if charge_info:
					raise NotImplementedError("Item-wise charges (charges affecting items) are not supported yet")

			elif is_charge_wise:
				if ref_idx is None:
					raise ValueError(f"Tax row {tax_row.as_dict()!r} is charge-wise but has no row_id")

				obj = object_by_idx[ref_idx]
				if not isinstance(obj, ChargeInfo):
					raise ValueError(
						f"Tax row {tax_row.as_dict()!r} is charge-wise but the referenced row {ref_idx} is not a charge, but is: {obj!r}"
					)

				if tax_info:
					if is_vat:
						if obj.vat is not None:
							raise ValueError(
								f"Tax row {tax_row.as_dict()!r} is charge-wise VAT but there is already a charge-wise VAT row for the same row_id"
							)
						obj.set_vat(tax_info)
					else:
						info.taxes.append(tax_info)

				if charge_info:
					raise NotImplementedError(
						"Charge-wise charges (charges affecting other charges) are not supported yet"
					)

		if discount := info.doc.discount_amount:  # type: ignore
			raise NotImplementedError("Document-level discounts are not supported yet")
			info.allowances.append(
				AllowanceInfo(
					amount=discount,
					reason="Discount",
					reason_code=None,
				)
			)

		# Compute totals
		info._gross_total = 0.0
		info._net_total = 0.0

		items_total = 0.0
		vat_total = 0.0
		others_total = 0.0
		allowances_total = 0.0  # positive

		for item in info.items:
			info._gross_total += item.price._gross_amount

			items_total += item.price._gross_amount
			vat_total += item.price._tax_amount

		for tax in info.taxes:  # other taxes
			raise NotImplementedError("Other taxes are not supported yet")

		for charge in info.charges:
			info._gross_total += charge.amount
			others_total += charge.amount

			if charge.vat:
				if charge.vat.amount is None:
					raise NotImplementedError("Charge-wise taxes with uncomputed amount are not supported yet")
				vat_total += charge.vat.amount

			for charge_tax in charge.taxes:
				raise NotImplementedError("Other taxes are not supported yet")

		for allowance in info.allowances:
			allowances_total += allowance.amount
			info._gross_total -= allowance.amount

		info._net_total = info._gross_total + vat_total

		info.subtotals.update(
			{
				"item": items_total,
				"other": others_total,
				"vat": vat_total,
				"allowance": allowances_total,
			}
		)

		info._check()

		return info

	def _check(self):
		if self.net_total != self.doc.grand_total:
			raise ValueError(
				f"{self!r}! Computed net total and charges does not match doc.grand_total: {self.net_total} != {self.doc.grand_total}"
			)

		if self._round(self.subtotal_vat + self.subtotal_charges) != self.doc.total_taxes_and_charges:
			raise ValueError(
				f"{self!r}! Computed total taxes and charges does not match doc.total_taxes_and_charges: {self.subtotal_vat} + {self.subtotal_charges} != {self.doc.total_taxes_and_charges}"
			)

	def __repr__(self):
		s = f"<{self.__class__.__name__}"
		if self.doc:
			s += f" of {self.doc!r}"
		s += ">"
		return s

	def _round(self, amount: float, precision=None) -> float:
		if precision is None:
			precision = 2
		if self.doc:
			precision = self.doc.precision("grand_total")
		return flt(amount, precision)

	@property
	def net_total(self):
		return self._round(self._net_total)

	@property
	def subtotal_vat(self) -> float:
		return self.subtotals["vat"]

	@property
	def subtotal_items(self) -> float:
		return self.subtotals["item"]

	@property
	def subtotal_charges(self) -> float:
		return self.subtotals["other"]

	@property
	def subtotal_allowances(self) -> float:
		return self.subtotals["allowance"]

	@property
	def vat_repartition_by_rate(self):
		"""
		Compute the VAT repartition by rate.
		"""

		def _zero(rate: float):
			return TaxInfo(
				amount=0.0,
				basis=0.0,
				percent=rate,
				tax_type="VAT",
				category="S",
				currency=self.currency,
			)

		def _make(tax_rate: float):
			if tax_rate not in by_rate:
				by_rate[tax_rate] = _zero(tax_rate)

		by_rate: dict[float, TaxInfo] = {}

		for item in self.items:
			tax_rate = item.price.tax_rate
			if tax_rate:
				_make(tax_rate)
				by_rate[tax_rate] += item.price.to_vat()

		for charge_info in self.charges:
			if charge_info.vat and charge_info.vat.percent:
				_make(charge_info.vat.percent)
				by_rate[charge_info.vat.percent] += charge_info.vat

		if self.document_wise_vat and by_rate:
			raise ValueError("Mixing document-wise VAT and item-wise VAT is not permitted")

		if self.document_wise_vat:
			by_rate[self.document_wise_vat.percent or 0.0] = self.document_wise_vat

		return by_rate

	@property
	def vat_repartition(self):
		return sorted(self.vat_repartition_by_rate.values(), key=lambda tax: tax.percent or 0.0)

	def as_html(self):
		def C(x: float):
			from frappe.utils import round_based_on_smallest_currency_fraction

			x = round_based_on_smallest_currency_fraction(x, self.currency, self.precision)
			x = frappe.format_value(
				x, df={"fieldtype": "Currency", "precision": self.precision}, currency=self.currency
			)
			return x

		def P(pct):
			return f"{100 * pct:.2f}".rstrip("0").rstrip(".") + " %"

		R = 'class="text-right"'

		o = "<h2>Invoice</h2>\n"

		o += "<h3>Items</h3>\n"
		o += "<table border=1 cellpadding=5>\n"
		cols = [
			("N°", "line_id"),
			("Article", "product_name"),
			("Qté", "quantity"),
			("Unité", "unit"),
			("PU HT", "gross_rate"),
			("TVA (%)", "tax_rate"),
			("Montant HT", "gross_amount"),
			("Montant TTC", "net_total"),
		]
		col_keys = [col[1] for col in cols]

		o += "<tr bgcolor=#ddd>" + "".join(f"<th>{col}</th>" for col, _ in cols) + "</tr>\n"
		o += "\n".join("<tr>" + item.as_html(col_keys) + "</tr>" for item in self.items)
		o += "</table>\n"

		o += "<h3>Frais</h3>\n"
		o += "<table border=1 cellpadding=5>\n"
		o += "<tr bgcolor=#ddd><th>Description</th><th>TVA (%)</th><th>Montant HT</th><th>Montant TTC</th></tr>\n"
		for charge in self.charges:
			charge_price = PriceCalcRounded.Basic(
				gross_amount=charge.amount,
				tax_rate=(charge.vat and charge.vat.percent) or 0.0,
				precision=self.precision,
				currency=self.currency,
			)
			o += "<tr>"
			o += f"<td>{charge.reason or ''}</td>"
			o += f"<td>{P(charge_price.tax_rate)}</td>"
			o += f"<td {R}>{C(charge_price.gross_amount)}</td>"
			o += f"<td {R}>{C(charge_price.net_total)}</td>"
			o += "</tr>\n"
		o += "</table>\n"

		o += "<h3>Totals</h3>\n"
		o += "<table border=1 cellpadding=5>\n"
		o += f"<tr style=font-size:small bgcolor=#ddd><th colspan=2>Total excl. VAT</th><td {R}>{C(self._gross_total)}</td></tr>\n"
		o += f"<tr style=font-size:smaller><td>&ndash;</td><th>Items</th><td {R}>{C(self.subtotals['item'])}</td></tr>\n"
		o += f"<tr style=font-size:smaller><td>&ndash;</td><th>Charges</th><td {R}>{C(self.subtotals['other'])}</td></tr>\n"

		o += f"<tr style=font-size:small bgcolor=#ddd><th colspan=2>VAT</th><td {R}>{C(self.subtotals['vat'])}</td></tr>\n"
		for vat in self.vat_repartition:
			pct = vat.percent or 0.0
			amt = vat.amount or 0.0
			o += (
				f"<tr style=font-size:smaller><td>&ndash;</td><th>{P(pct)}</th><td {R}>{C(amt)}</td></tr>\n"
			)

		o += f"<tr style=font-size:large bgcolor=#ddd><th colspan=2>Total incl. VAT</th><td style=font-weight:bold {R}>{C(self._net_total)}</td></tr>\n"
		o += "</table>\n"

		o += "<h3>Payment</h3>\n"
		o += "<table border=1 cellpadding=5>\n"
		o += f"<tr><th colspan=2>Issue date</th><td>{self.doc.posting_date}</td></tr>\n"
		o += f"<tr><th colspan=2>Due date</th><td>{self.doc.due_date}</td></tr>\n"

		o += f"<tr><th colspan=2>Total advance</th><td>{C(self.doc.total_advance)}</td></tr>\n"
		o += f"<tr><th colspan=2>Outstanding amount</th><td>{C(self.doc.outstanding_amount)}</td></tr>\n"

		o += "<tr><th colspan=2>Payment schedule</th><td></td></tr>\n"
		for s in self.doc.payment_schedule:
			o += f"<tr style=font-size:smaller><td>&ndash;</td><th>{s.due_date}</th><td>{C(s.payment_amount)} ({P(s.invoice_portion / 100)})</td></tr>\n"

		o += "</table>\n"

		# Basic values
		o += "<h3>Basic checks</h3>\n"
		o += "<ul>\n"

		o += f"<li>Net total: {self.net_total} (should be {(self.doc.grand_total)}, raw value is: {self._net_total})</li>\n"

		total = self.subtotals["item"]
		o += (
			f"<li>Items: {self._round(total)} (should be {(self.doc.total)}, raw value is: {total})</li>\n"
		)

		total_taxes_and_charges = self.subtotals["other"] + self.subtotals["vat"]
		o += f"<li>Taxes + Charges: {self._round(total_taxes_and_charges)} (should be {(self.doc.total_taxes_and_charges)}, raw value is: {total_taxes_and_charges})</li>\n"

		o += "</ul>\n"

		return o
