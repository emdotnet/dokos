from dataclasses import dataclass
from datetime import datetime

import frappe

from .id import IdInfo
from .price import PriceCalcRounded
from .tax import TaxInfo


@dataclass
class PriceInfo:
	amout: float


@dataclass
class TimePeriodInfo:
	start: datetime | None
	end: datetime | None


@dataclass
class ProductInfo:
	name: str
	description: str | None = None
	country_of_origin: str | None = None

	id_global: IdInfo | None = None
	id_seller: IdInfo | None = None
	id_buyer: IdInfo | None = None

	@classmethod
	def FromItem(cls, item, row):
		row = row or {}
		if isinstance(item, str):
			item = frappe.get_doc("Item", item)

		barcode: str | None = row.get("barcode") or None
		item_name: str = row.get("item_name", item.item_name)  # type: ignore
		description: str | None = row.get("description", item.description) or None  # type: ignore

		if item.country_of_origin:
			country_code = str(frappe.get_value("Country", item.country_of_origin, "code")).upper()
		else:
			country_code = None

		return cls(
			name=item_name,
			description=description or None,
			country_of_origin=country_code,
			id_global=IdInfo.Barcode(barcode) if barcode else None,
			id_seller=IdInfo(item.item_code, "", "ram:SellerAssignedID"),
			id_buyer=None,
		)

	def __repr__(self):
		return f"[Product {self.name!r}]"

	def as_xml(self, fmt) -> str:
		return fmt.render("product", {"product": self})


@dataclass
class ItemInfo:
	line_id: int
	product: ProductInfo

	# Price
	price: PriceCalcRounded

	tax: TaxInfo | None = None
	time_period: TimePeriodInfo | None = None

	# allowances: list[AllowanceInfo] = field(default_factory=list)
	# charges: list[ChargeInfo] = field(default_factory=list)

	@classmethod
	def FromSalesInvoiceItemRow(
		cls, sinv: "frappe.Document", row: "frappe.Document | int", tax_rate: float
	):
		if isinstance(row, int):
			row = sinv.items[row]  # type: ignore

		# Gross unit price / Prix unitaire HT / Bruttopreis pro Einheit
		# NOTE: The gross rate seems to be stored in the net_rate field for some reason,
		# even in the case of an excluded tax rate.
		gross_rate = float(row.net_rate)  # type: ignore
		quantity = float(row.qty)  # type: ignore

		currency: str = sinv.currency  # type: ignore
		precision = sinv.precision("net_rate", "items") or 2
		uom: str = row.uom  # type: ignore

		price = PriceCalcRounded(quantity, gross_rate, tax_rate, currency, precision, uom)

		return cls(
			line_id=row.idx,  # type: ignore
			product=ProductInfo.FromItem(row.item_code, row),  # type: ignore
			price=price,
			tax=price.to_vat(),
		)

	def __repr__(self):
		return f"[Item #{self.line_id!r} {self.product!r} {self.price!r}]"

	def as_html(self, columns: list[str]):
		mapping = {
			"line_id": lambda: f"#{self.line_id}",
			"product_name": lambda: self.product.name,
			"quantity": lambda: self.price.quantity,
			"unit": lambda: self.price.uom,
			"tax_rate": lambda: f"{self.price._fmt_percent(self.price.tax_rate)}",
			"gross_rate": lambda: self.price._fmt(self.price.gross_rate),
			"gross_amount": lambda: self.price._fmt(self.price.gross_amount),
			"net_total": lambda: self.price._fmt(self.price.net_total),
		}
		right = {"gross_rate", "gross_amount", "net_total"}

		def v(name: str):
			s = mapping[name]()
			if name in right:
				return f"<td align='right'>{s}</td>"
			else:
				return f"<td>{s}</td>"

		return "".join([v(c) for c in columns])

	def as_xml(self, fmt):
		return fmt.render("item", {"item": self})
