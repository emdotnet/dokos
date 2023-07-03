from typing import Literal

import frappe
from frappe.utils import round_based_on_smallest_currency_fraction

from ..uoms import get_unece_rec20_code_for_uom
from .tax import TaxInfo


def _assert(cond: bool, msg: str):
	if not cond:
		raise frappe.ValidationError(msg)


class PriceCalcRounded:
	quantity: float
	_gross_rate: float
	tax_rate: float
	currency: str | Literal[""]
	precision: int
	uom: str

	def __init__(
		self,
		quantity: float,
		gross_rate: float,
		tax_rate: float,
		currency: str,
		precision: int,
		uom: str,
	):
		_assert(isinstance(precision, int), f"Precision must be an integer, got: {precision!r}")
		_assert(isinstance(currency, str), f"Currency must be a string, got: {currency!r}")
		_assert(isinstance(gross_rate, (float, int)), f"Gross rate must be a float, got: {gross_rate!r}")
		_assert(isinstance(tax_rate, (float, int)), f"Tax rate must be a float, got: {tax_rate!r}")
		_assert(isinstance(quantity, (float, int)), f"Quantity must be a float, got: {quantity!r}")
		_assert(isinstance(uom, str), f"UOM must be a string, got: {uom!r}")
		_assert(0 <= precision, f"Precision must be positive or zero, got: {precision!r}")
		_assert(0 <= tax_rate <= 1, f"Tax rate must be between 0 and 1, got: {tax_rate!r}")
		_assert(quantity > 0, f"Quantity must be strictly positive, got: {quantity!r}")

		self.quantity = float(quantity)
		self._gross_rate = float(gross_rate)
		self.tax_rate = float(tax_rate)
		self.currency = currency
		self.precision = precision
		self.uom = uom

	@classmethod
	def Basic(
		cls, gross_amount: float, tax_rate: float, precision: int, currency=""
	) -> "PriceCalcRounded":
		return PriceCalcRounded(
			quantity=1,
			gross_rate=gross_amount,
			tax_rate=tax_rate,
			currency=currency,
			precision=precision,
			uom="one",
		)

	def to_vat(self) -> TaxInfo | None:
		return TaxInfo(
			tax_type="VAT",
			category="S",
			percent=self.tax_rate,
			basis=self.gross_amount,
			amount=self.tax_amount,
			currency=self.currency,
		)

	# Utils
	def __repr__(self) -> str:
		S = self.currency_symbol
		a = f"{self.quantity} {self.uom} [{self.unit_code}] × {self.gross_rate}{S}"

		if self.tax_rate == 0:
			return f"{a} = {self.net_total}{S} (not taxed)"

		return f"{a} ({self.net_rate}{S} net rate) + {100 * self.tax_rate}% VAT ({self.tax_amount}{S}) = {self.gross_amount}{S} ({self.net_total}{S} net total)"

	@property
	def currency_symbol(self) -> str:
		if self.currency:
			return frappe.db.get_value("Currency", self.currency, "symbol") or self.currency
		else:
			return "¤"

	def _round(self, x: float) -> float:
		return round_based_on_smallest_currency_fraction(x, self.currency, self.precision)

	def _taxed(self, x: float) -> float:
		return x * (1 + self.tax_rate)

	def _untaxed(self, x: float) -> float:
		return x / (1 + self.tax_rate)

	def _fmt(self, x: float) -> str:
		return frappe.format_value(
			x, df={"fieldtype": "Currency", "precision": self.precision}, currency=self.currency
		)

	def _fmt_percent(self, x: float) -> str:
		_assert(0 <= x <= 1, f"Percentage must be between 0 and 1, got: {x!r}")
		return f"{100 * x:.1f}".rstrip("0").rstrip(".") + " %"
		# return frappe.format_value(100 * x, df={"fieldtype": "Percent"})

	# Raw (unrounded) values
	@property
	def _net_rate(self) -> float:
		return self._taxed(self._gross_rate)

	@property
	def _gross_amount(self) -> float:
		return self.gross_rate * self.quantity

	@property
	def _tax_amount(self) -> float:
		return self._net_total - self._gross_amount

	@property
	def _net_total(self) -> float:
		return self._taxed(self._gross_amount)

	# Rounded values
	@property
	def gross_rate(self) -> float:
		return self._round(self._gross_rate)

	@property
	def net_rate(self) -> float:
		return self._round(self._net_rate)

	@property
	def gross_amount(self) -> float:
		return self._round(self._gross_amount)

	@property
	def tax_amount(self) -> float:
		return self._round(self._tax_amount)

	@property
	def net_total(self) -> float:
		return self._round(self._net_total)

	# Other values
	@property
	def unit_code(self) -> str:
		return get_unece_rec20_code_for_uom(self.uom)

	def as_html(self) -> str:
		S = self.currency_symbol
		if self.tax_rate == 0:
			return f"{self.quantity} {self.uom} × {self.gross_rate}{S} = {self.net_total}{S} (not taxed)"
		return f"{self.quantity} {self.uom} × {self.gross_rate}{S} + {100 * self.tax_rate}% VAT = {self.net_total}{S}"
