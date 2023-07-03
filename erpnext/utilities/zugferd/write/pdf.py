from facturx import generate_from_binary
from facturx.facturx import logger

logger.setLevel("DEBUG")


def add_zugferd_xml_to_pdf(pdf: bytes, xml: str | bytes):
	return add_facturx_xml_to_pdf(pdf, xml)


def add_facturx_xml_to_pdf(pdf: bytes, xml: str | bytes):
	"""Add ZUGFeRD/Factur-X XML to PDF"""

	if not xml:
		return

	if not isinstance(xml, (bytes, str)):
		raise TypeError(
			f"add_facturx_xml_to_pdf method should receive a bytes | string | None, got value: {xml!r}"
		)

	if isinstance(xml, str):
		xml = xml.encode("utf-8")

	# try:
	# 	# return "<pre><code>" + xml.replace("<", "&lt;").replace(">", "&gt;") + "</code></pre>"
	# 	from xml.etree import cElementTree as ET
	# 	root = ET.ElementTree(ET.fromstring(xml)).getroot()
	# 	ET.indent(root, space="    ", level=0)
	# 	out: bytes = ET.tostring(root, encoding="UTF-8", method="xml")
	# 	return "<pre>" + out.decode("utf-8").replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
	# except Exception:
	# 	print(xml)
	# 	raise

	try:
		return generate_from_binary(pdf, xml, level="extended")
	except Exception:
		txt = xml.decode("utf-8")
		print()
		print()
		print(txt)
		print()
		print()
		txt = "\n".join(f"{i:3d}\t{line}" for i, line in enumerate(txt.splitlines(), 1))
		raise Exception(f"Invalid Factur-X XML:\n{txt}")
