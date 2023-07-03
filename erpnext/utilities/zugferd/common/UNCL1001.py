# https://service.unece.org/trade/untdid/d99a/uncl/uncl1001.htm
# https://docs.peppol.eu/poacc/billing/3.0/codelist/UNCL1001-inv/

import frappe


class UNCL1001:
	@classmethod
	def from_doc(cls, doc: "frappe.Document") -> str:
		if not doc.doctype:
			raise ValueError("doc.doctype is not set")
		# ... = frappe.get_all("eInvoicing Mapping for Doctype", ["code", "conditions"], filters={"doctype": doc.doctype})

		simple_mapping = {
			"Payment Request": "71",
		}
		if code := simple_mapping.get(doc.doctype):
			return code

		if doc.doctype == "Sales Invoice" or doc.doctype == "Purchase Invoice":
			# TODO: Check if the invoice is a credit note, debit note, etc.
			return "380"  # Commercial invoice

		return "130"

	@classmethod
	def doctype_from_code(cls, code: str) -> str:
		if code == "380":
			return "Sales Invoice"
		raise NotImplementedError(f"UNCL1001.doctype_from_code({code})")


#  71 Request for payment
#  80 Debit note related to goods or services
#  82 Metered services invoice (e.g., gas, electricity, etc.)
#  84 Debit note related to financial adjustments
# 102 Tax notification
# 218 Final payment request (of a series of payment requests) based on completion of work
# 219 Payment request for completed units
# 331 Commercial invoice which includes a packing list
# 380 Commercial invoice
# 382 Commission note
# 383 Debit note
# 386 Prepayment invoice (to pay in advance)
# 388 Tax invoice
# 393 Factored invoice (assigned to a third party for collection)
# 395 Consignment invoice (an invoice for goods sent to a party that is not the owner but that is responsible for selling the goods or returning them if not sold)
# 553 Forwarder's invoice discrepancy report (reporting discrepancies indentified by the freight forwarder)
# 575 Insurer's invoice (issued by an insurer claiming payment of an insurance which has been effected)
# 623 Forwarder's invoice (issued by a freight forwarder claiming payment for services rendered and costs incurred)
# 780 Freight invoice
# 817 Claim notification
# 870 Consular invoice
# 875 Partial construction invoice
# 876 Partial final construction invoice
# 877 Final construction invoice
