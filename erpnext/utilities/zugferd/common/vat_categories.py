class TaxCategoryCode:
	_codes = {
		"AE": "Vat Reverse Charge",
		"E": "Exempt from Tax",
		"S": "Standard rate",
		"Z": "Zero rated goods",
		"G": "Free export item, tax not charged",
		"O": "Services outside scope of tax",
		"K": "VAT exempt for EEA intra-community supply of goods and services",
		"L": "Canary Islands general indirect tax",
		"M": "Tax for production, services and importation in Ceuta and Melilla",
	}

	@classmethod
	def describe(cls, code: str) -> str:
		return cls._codes.get(code, "")
