from xml.dom import minidom

import frappe
from facturx import check_facturx_xsd

import erpnext.utilities.zugferd.write.renderers as renderers
from erpnext.utilities.zugferd.common.data.sinv import SalesInvoiceInfo
from erpnext.utilities.zugferd.read.from_xml import extract_terms_from_xml
from erpnext.utilities.zugferd.write.pdf import add_facturx_xml_to_pdf


@frappe.whitelist()
def facturx(doctype: str, name: str) -> str | bytes | None:
	doc = frappe.get_doc(doctype, name)

	xml: str = get_doc_as_facturx_xml(doc)  # type: ignore

	try:
		xml = minidom.parseString(xml).toprettyxml(indent="  ")
		check_facturx_xsd(xml.encode("utf-8"), facturx_level="extended")
	except Exception:
		txt = "\n".join(f"{i:3d}\t{line}" for i, line in enumerate(xml.splitlines(), 1))
		raise Exception(f"Invalid Factur-X XML:\n{txt}")

	html = ""

	terms = extract_terms_from_xml(xml)
	html += "<h3>Terms</h3><ul>"
	for k, v in terms.items():
		html += f"<li><b>{k}</b>: {v!r}</li>"
	html += "</ul>"

	html += (
		f'<pre class="p-1" style="font-size:10px;">{xml.replace("<", "&lt;").replace(">", "&gt;")}</pre>'
	)
	html += "<br><br><hr>" + SalesInvoiceInfo.FromDoc(doc).as_html()
	frappe.respond_as_web_page(title="Factur-X XML", html=html)
	return


def get_doc_as_facturx_xml(doc: "frappe.Document") -> str | bytes | None:
	if doc.doctype == "Sales Invoice":  # and doc.docstatus == 1:
		return renderers.SalesInvoiceRenderer().render(doc)  # type: ignore


def postprocess_pdf(*, pdf: bytes, doc: "frappe.Document", **kwargs):
	try:
		if xml := get_doc_as_facturx_xml(doc):
			xml = minidom.parseString(xml).toprettyxml()
			return add_facturx_xml_to_pdf(pdf, xml)
	except Exception:
		if frappe.conf.developer_mode:
			raise
		else:
			frappe.log_error(
				title="ZUGFeRD/Factur-X generation failed",
				reference_doctype=doc.doctype,
				reference_name=doc.name,
			)
