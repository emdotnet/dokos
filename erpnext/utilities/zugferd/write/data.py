from dataclasses import dataclass
from typing import TYPE_CHECKING

import frappe

from ..common.types import AddressInfo, ContactInfo, PartyInfo
from .formatter import BaseFormatter

if TYPE_CHECKING:
	from ..common import types as t


class Utils:
	@classmethod
	def get_default_address(cls, doctype: str, docname: str) -> "t.Address | None":
		from frappe.contacts.doctype.address.address import get_default_address

		address_name = get_default_address(doctype, docname)  # type: ignore
		return frappe.get_doc("Address", address_name) if address_name else None  # type: ignore

	@classmethod
	def get_default_contact(cls, doctype: str, docname: str) -> "t.Contact | None":
		from frappe.contacts.doctype.contact.contact import get_default_contact

		contact_name = get_default_contact(doctype, docname)  # type: ignore
		return frappe.get_doc("Contact", contact_name) if contact_name else None  # type: ignore

	@classmethod
	def get_contact_display_name(cls, doc: "frappe.Document | None") -> str:
		from frappe.contacts.doctype.contact.contact import get_contact_details

		if not doc:
			return ""

		return get_contact_details(doc.name).get("contact_display", "")  # type: ignore


@dataclass
class SellerInfo(PartyInfo):
	id: str  # Internal identifier
	name: str  # Display name
	global_id: str | None  # Globally unique identifier
	vat_id: str | None  # Local VAT identifier
	address_info: AddressInfo
	contact_info: ContactInfo

	@classmethod
	def FromCompany(cls, company: "t.Company") -> "SellerInfo":
		contact = Utils.get_default_contact("Company", company.name)  # type: ignore
		address = Utils.get_default_address("Company", company.name)  # type: ignore
		if not address:
			raise ValueError(f"{company.name!r} is not linked to any address")

		def _find_val(keys: list[str]):
			for doc in (company, contact, address):
				for key in keys:
					if value := getattr(doc, key, None):
						return value
			return None

		address_info = AddressInfo.FromAddress(address)
		contact_info = ContactInfo(
			person_name=Utils.get_contact_display_name(contact) or company.name,  # type: ignore
			phone=_find_val(["phone_no", "phone", "mobile_no"]),
			fax=_find_val(["fax"]),
			email=_find_val(["email", "email_id"]),
		)
		return SellerInfo(
			id=company.name,  # type: ignore
			name=company.name,  # type: ignore
			global_id="",  # TODO
			vat_id=_find_val(["tax_id"]),
			address_info=address_info,
			contact_info=contact_info,
		)

	def as_xml(self, fmt: BaseFormatter) -> str:
		return fmt.party("ram:SellerTradeParty", self)


@dataclass
class BuyerInfo(PartyInfo):
	id: str
	name: str
	global_id: str | None
	vat_id: str | None
	address_info: AddressInfo
	contact_info: ContactInfo

	@classmethod
	def FromDoc(cls, doc: "t.SalesInvoice"):
		customer_name: str = doc.customer
		customer: "t.Customer" = frappe.get_doc("Customer", customer_name)  # type: ignore

		# Address
		address_name: str = (
			doc.customer_address  # type: ignore
			# or doc.shipping_address_name
			or doc.company_address  # type: ignore
			or customer.customer_primary_address  # type: ignore
			or Utils.get_default_address("Customer", customer.name)  # type: ignore
		)  # type: ignore

		if not address_name or not isinstance(address_name, str):
			raise TypeError(f"Unable to find address name in document {doc!r}")

		address: "t.Address" = frappe.get_doc("Address", address_name)  # type: ignore
		address_info = AddressInfo.FromAddress(address)

		# Contact
		contact_name: str = (
			doc.contact_person  # type: ignore
			or customer.customer_primary_contact  # type: ignore
			or Utils.get_default_contact("Customer", customer.name)  # type: ignore
		)  # type: ignore

		if not contact_name or not isinstance(contact_name, str):
			raise TypeError(f"Unable to find contact name in document {doc!r}")

		contact: "t.Contact" = frappe.get_doc("Contact", contact_name)  # type: ignore
		contact_info = ContactInfo(
			person_name=Utils.get_contact_display_name(contact),  # type: ignore
			email=doc.contact_email or contact.email_id or address.email_id,  # type: ignore
			phone=doc.contact_mobile or contact.phone or contact.mobile_no or address.phone,  # type: ignore
			fax=address.fax,  # type: ignore
		)

		return BuyerInfo(
			id=customer.name,  # type: ignore
			name=doc.customer_name or customer.name,  # type: ignore
			global_id=None,
			vat_id=doc.company_tax_id or None,  # type: ignore
			address_info=address_info,
			contact_info=contact_info,
		)

	def as_xml(self, fmt: BaseFormatter) -> str:
		return fmt.party("ram:BuyerTradeParty", self)
