import datetime

import frappe
from frappe.utils.dateutils import getdate

from ..common.types import AddressInfo, ContactInfo, PartyInfo
from .exceptions import EInvoiceInvalidValueError, EInvoiceRequiredValueError


def E(value: str) -> str:
	"""Escape characters for XML interpolation"""
	return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def MergedContext(*contexts: dict):
	"""Merge multiple contexts into one"""
	result = frappe._dict()
	for ctx in contexts:
		result.update(ctx or {})
	return result


class BaseFormatter:
	def __init__(self, global_context, template_paths):
		self.global_context = global_context
		self.templates = {name: frappe.get_template(path) for name, path in template_paths.items()}

	@property
	def context(self) -> frappe._dict:
		return self.global_context

	def E(self, value: str) -> str:
		return E(value)

	def render(self, template_name: str, ctx: dict):
		if template_name not in self.templates:
			raise ValueError(f"Unregistered template {template_name!r}")
		return self.templates[template_name].render(MergedContext(ctx, self.global_context))

	def currency(self, value: float):
		if not isinstance(value, (float, int)):
			raise TypeError(f"Expected float, got {type(value)}: {value!r}")
		precision = self.global_context.get("precision", 2)
		return f"{value:.{precision}f}"

	def uom(self, uom: str):
		from ..common.uoms import get_unece_rec20_code_for_uom

		code = get_unece_rec20_code_for_uom(uom)
		if code == "C62":
			print("Warning: UOM could not be mapped to UNECE Rec20 code:", uom)
		return code

	def date(self, value: str | datetime.date | datetime.datetime):
		date = getdate(value) if value else None
		if not date:
			raise EInvoiceRequiredValueError("date")

		formatted: str = date.strftime("%Y%m%d")
		return f'<udt:DateTimeString format="102">{E(formatted)}</udt:DateTimeString>'

	def id(self, value: str, scheme="", type="ram:ID"):
		if not value:
			raise EInvoiceRequiredValueError("id")

		attrs = f' schemeID="{scheme}"' if scheme else ""
		return f"<{type}{attrs}>{E(value)}</{type}>"

	def address(self, addr: AddressInfo | None):
		if not addr:
			return ""

		body = ""

		if v := addr.pincode:
			body += f"<ram:PostcodeCode>{E(v)}</ram:PostcodeCode>\n"
		if v := addr.address_line1:
			body += f"<ram:LineOne>{E(v)}</ram:LineOne>\n"
		if v := addr.address_line2:
			body += f"<ram:LineTwo>{E(v)}</ram:LineTwo>\n"
		if v := addr.city:
			body += f"<ram:CityName>{E(v)}</ram:CityName>\n"
		if v := addr.country_code:
			body += f"<ram:CountryID>{self.country(v)}</ram:CountryID>\n"

		if not body:
			return ""
		return f"<ram:PostalTradeAddress>\n{body}</ram:PostalTradeAddress>"

	def country(self, value: str):
		if not value:
			raise EInvoiceRequiredValueError("country")

		if isinstance(value, str) and len(value) == 2:
			return E(value.upper())

		raise EInvoiceInvalidValueError(f"Invalid country code: {value!r}")

	def contact(self, contact_info: ContactInfo | None):
		"""
		<xs:element name="PersonName" type="udt:TextType" minOccurs="0"/>
		<xs:element name="DepartmentName" type="udt:TextType" minOccurs="0"/>
		?<xs:element name="TypeCode" type="qdt:ContactTypeCodeType" minOccurs="0"/>
		<xs:element name="TelephoneUniversalCommunication" type="ram:UniversalCommunicationType" minOccurs="0"/>
		?<xs:element name="FaxUniversalCommunication" type="ram:UniversalCommunicationType" minOccurs="0"/>
		<xs:element name="EmailURIUniversalCommunication" type="ram:UniversalCommunicationType" minOccurs="0"/>
		"""

		if not contact_info:
			return ""

		body = ""
		if person_name := contact_info.person_name:
			body += f"<ram:PersonName>{E(person_name)}</ram:PersonName>\n"
		if phone := contact_info.phone:
			body += f"<ram:TelephoneUniversalCommunication><ram:CompleteNumber>{self.international_phone_number(phone)}</ram:CompleteNumber></ram:TelephoneUniversalCommunication>\n"
		# if fax := contact_info.fax:
		# 	body += f"<ram:FaxUniversalCommunication><ram:CompleteNumber>{self.international_phone_number(fax)}</ram:CompleteNumber></ram:FaxUniversalCommunication>\n"
		if email := contact_info.email:
			body += f"<ram:EmailURIUniversalCommunication><ram:URIID>{E(email)}</ram:URIID></ram:EmailURIUniversalCommunication>\n"

		if not body:
			return ""

		return f"<ram:DefinedTradeContact>\n{body}</ram:DefinedTradeContact>"

	def party(self, element: str, party: PartyInfo):
		"""
		<xs:element name="ID" type="udt:IDType" minOccurs="0" maxOccurs="unbounded"/>
		<xs:element name="GlobalID" type="udt:IDType" minOccurs="0" maxOccurs="unbounded"/>
		<xs:element name="Name" type="udt:TextType" minOccurs="0"/>
		<xs:element name="Description" type="udt:TextType" minOccurs="0"/>
		<xs:element name="SpecifiedLegalOrganization" type="ram:LegalOrganizationType" minOccurs="0"/>
		<xs:element name="DefinedTradeContact" type="ram:TradeContactType" minOccurs="0"/>
		<xs:element name="PostalTradeAddress" type="ram:TradeAddressType" minOccurs="0"/>
		<xs:element name="URIUniversalCommunication" type="ram:UniversalCommunicationType" minOccurs="0"/>
		<xs:element name="SpecifiedTaxRegistration" type="ram:TaxRegistrationType" minOccurs="0" maxOccurs="2"/>
		"""

		body = ""

		if v := party.id:
			body += self.id(v)
		if v := party.global_id:
			body += self.id(v, scheme="0088", type="ram:GlobalID")

		body += f"<ram:Name>{E(party.name)}</ram:Name>"

		# if v := party.description:
		# 	body += f"<ram:Name>{E(party.description)}</ram:Name>"

		body += self.contact(party.contact_info)
		body += self.address(party.address_info)

		if v := party.vat_id:
			body += (
				f"<ram:SpecifiedTaxRegistration>{self.id(v, scheme='VA')}</ram:SpecifiedTaxRegistration>"
			)

		return f"<{element}>{body}</{element}>"

	def international_phone_number(self, value: str):
		import phonenumbers

		if not value:
			raise EInvoiceRequiredValueError("international_phone_number")

		# parse the phone number which might be in national format and convert it to international format
		phone = phonenumbers.parse(value, "FR")  # TODO: get country code from doc.company?
		return E(phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164))
