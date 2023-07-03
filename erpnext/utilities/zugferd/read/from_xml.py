# https://www.impots.gouv.fr/sites/default/files/media/1_metier/2_professionnel/EV/2_gestion/290_facturation_electronique/annexe_1_-_format_semantique_b2b_e-invoicing_-_flux_12.xlsx

from datetime import datetime
from functools import partial

from bs4 import BeautifulSoup, Tag

business_terms_xpath = {
	"BT-1": "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:ID",
	"BT-2": "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
	"BT-3": "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:TypeCode",
	"BT-5": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
	"BT-6": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:TaxCurrencyCode",
	"BT-7": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:TaxPointDate/udt:DateString",
	"BT-9": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString",
	"BT-10": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference",
	"BT-110": "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount",
}


def _query(dom: BeautifulSoup, css_selector: str):
	elements = dom.select(css_selector.lstrip("/").replace("/", " > ").replace(":", "\\:"))
	if not elements:
		return None
	if len(elements) > 1:
		return [e for e in elements]
	return elements[0]


def _parse_bt(bt_type: str, node: Tag):
	t = node.text.strip()

	if bt_type == "udt:DateTimeString":
		if node.attrs["format"] == "102":
			return datetime.strptime(t, "%Y%m%d").date()
		raise Exception(f"FailedParse: Unknown DateTimeString format {node.attrs['format']!r}")

	return t


def _query_bt(dom: BeautifulSoup, bt: str, bt_xpath: str | None = None):
	bt_xpath = bt_xpath or business_terms_xpath.get(bt)
	if not bt_xpath:
		raise Exception(f"FailedQuery: Business Term {bt!r} not found")

	res = _query(dom, bt_xpath)

	if res is None:
		return None

	bt_type = bt_xpath.split("/")[-1]
	if isinstance(res, list):
		return [_parse_bt(bt_type, e) for e in res]
	return _parse_bt(bt_type, res)


def extract_terms_from_xml(xml: str | bytes):
	dom = BeautifulSoup(xml, "lxml")

	query = partial(_query, dom)
	query_bt = partial(_query_bt, dom)

	out = {}
	for bt, bt_xpath in business_terms_xpath.items():
		if res := query_bt(bt, bt_xpath):
			out[bt] = res

	return out
