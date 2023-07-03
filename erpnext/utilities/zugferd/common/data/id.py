from dataclasses import dataclass


@dataclass
class IdInfo:
	value: str
	scheme: str = ""
	type: str = "ram:ID"

	@classmethod
	def Barcode(cls, value: str):
		return IdInfo(value=value, scheme="0160", type="ram:GlobalID")

	def as_xml(self, fmt) -> str:
		return str(self)

	def __str__(self) -> str:
		value = self.value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
		attrs = f' schemeID="{self.scheme}"' if self.scheme else ""
		return f"<{self.type}{attrs}>{value}</{self.type}>"
