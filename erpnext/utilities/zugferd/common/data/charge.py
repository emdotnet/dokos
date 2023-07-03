from dataclasses import dataclass, field

from .tax import TaxInfo


@dataclass
class AllowanceChargeInfo:
	amount: float
	is_charge: bool  # true -> charge, false -> allowance

	percent: float | None = None
	basis: float | None = None
	vat: TaxInfo | None = None
	taxes: list[TaxInfo] = field(default_factory=list)
	reason_code: str | None = None
	reason: str | None = None

	def as_xml(self, fmt) -> str:
		return fmt.render("allowance_charge", self.__dict__)

	def set_vat(self, vat: TaxInfo):
		self.vat = vat.copy()
		if self.vat.percent:
			self.vat.basis = self.amount
			self.vat.amount = self.amount * self.vat.percent


@dataclass
class AllowanceInfo(AllowanceChargeInfo):
	is_charge: bool = False


@dataclass
class ChargeInfo(AllowanceChargeInfo):
	is_charge: bool = True
