from dataclasses import dataclass
from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from frappe.contacts.doctype.address.address import Address  # noqa
	from frappe.contacts.doctype.contact.contact import Contact  # noqa

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice  # noqa
	from erpnext.accounts.doctype.sales_invoice_item.sales_invoice_item import (  # noqa
		SalesInvoiceItem,
	)
	from erpnext.selling.doctype.customer.customer import Customer  # noqa
	from erpnext.setup.doctype.company.company import Company  # noqa


@dataclass
class AddressInfo:
	address_line1: str | None
	address_line2: str | None
	pincode: str | None
	city: str | None
	country_code: str | None

	@classmethod
	def FromAddress(cls, addr: "Address"):
		country_code: str = frappe.get_value("Country", addr.country, "code").upper()  # type: ignore
		return AddressInfo(
			address_line1=addr.address_line1,  # type: ignore
			address_line2=addr.address_line2,  # type: ignore
			pincode=addr.pincode,  # type: ignore
			city=addr.city,  # type: ignore
			country_code=country_code,
		)


@dataclass
class ContactInfo:
	person_name: str | None
	phone: str | None
	fax: str | None
	email: str | None
	id: str | None = None

	@classmethod
	def FromContactName(cls, contact_name: str):
		from frappe.contacts.doctype.contact.contact import get_contact_details

		details = get_contact_details(contact_name)
		print(details)
		return ContactInfo(
			id=details.get("contact_person"),
			person_name=details.get("contact_display"),
			phone=details.get("contact_phone") or details.get("contact_mobile"),
			fax="",
			email=details.get("contact_email"),
		)


class PartyInfo:
	id: str
	name: str
	global_id: str | None
	vat_id: str | None
	address_info: AddressInfo
	contact_info: ContactInfo
