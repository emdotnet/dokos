import frappe


class EInvoiceError(frappe.ValidationError):
	"""Base class for all errors raised by this module."""

	pass


class EInvoiceRequiredValueError(EInvoiceError):
	"""Raised when a required value is not found in the document."""

	pass


class EInvoiceInvalidValueError(EInvoiceError):
	"""Raised when a value is not valid for the document."""

	pass
