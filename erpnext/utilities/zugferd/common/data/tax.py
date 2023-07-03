from dataclasses import dataclass
from typing import Literal


@dataclass
class TaxInfo:
	tax_type: Literal["VAT", "?"]
	category: Literal["S"]

	percent: float | None = None
	amount: float | None = None
	basis: float | None = None
	currency: str | None = None

	def __post_init__(self):
		if self.percent is not None:
			if self.percent < 0:
				raise ValueError("Percent cannot be negative")
			if self.percent > 1:
				raise ValueError("Percent cannot be greater than 1.0 (100%), got: " + str(self.percent))

	# TaxPointDate
	# DueDateTypeCode
	# ExemptionReason
	# ExemptionReasonCode

	def as_xml(self, fmt, **kwargs) -> str:
		return fmt.render("tax", {"tax": self, **kwargs})

	# @classmethod
	# def VatFromRate(cls, percent: float, **kwargs):
	# 	return TaxInfo(percent=percent, tax_type="VAT", category="S", **kwargs)

	def __add__(self, other):
		if isinstance(other, TaxInfo):
			if self.percent != other.percent:
				raise ValueError("Cannot perform addition for TaxInfo objects with different 'percent'")
			if self.tax_type != other.tax_type:
				raise ValueError("Cannot perform addition for TaxInfo objects with different 'tax_type'")
			if self.category != other.category:
				raise ValueError("Cannot perform addition for TaxInfo objects with different 'category'")

			return TaxInfo(
				percent=self.percent,
				tax_type=self.tax_type,
				category=self.category,
				amount=(self.amount or 0.0) + (other.amount or 0.0),
				basis=(self.basis or 0.0) + (other.basis or 0.0),
				currency=self.currency or other.currency,
			)
		else:
			return NotImplemented

	def copy(self):
		return TaxInfo(**self.__dict__)
