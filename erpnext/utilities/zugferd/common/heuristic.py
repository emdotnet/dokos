import frappe


def get_country_code_of_company(company_name: str) -> str:
	country_name = frappe.get_value("Company", company_name, "country")
	country_code: str = frappe.get_value("Country", country_name, "code")  # type: ignore
	return country_code.upper()


def tax_row_is_vat(tax_row: frappe._dict):
	return account_is_vat(tax_row.account_head)  # type: ignore


def account_is_vat(account_name: str):
	account = frappe.get_doc("Account", account_name)  # type: ignore

	if get_country_code_of_company(account.company) == "FR":
		if account.account_type == "Tax":
			if account.name.startswith("445"):
				# https://www.comptabilisation.fr/files/pcg-plan-comptable-general.pdf
				return True

	return False


def tax_row_is_item_wise(tax_row: frappe._dict):
	return tax_row.charge_type == "On Net Total" and tax_row.rate == 0


def tax_row_is_charge_wise(tax_row: frappe._dict) -> bool:
	return "Previous" in tax_row.charge_type  # type: ignore


def tax_row_is_other_charge(tax_row: frappe._dict) -> bool:
	return tax_row.charge_type == "Actual"


def get_charge_reason(tax_row: frappe._dict):
	account = frappe.get_doc("Account", tax_row.account_head)  # type: ignore

	if get_country_code_of_company(account.company) == "FR":
		if account.account_type == "Tax":
			if account.name.startswith("7085"):
				# https://www.memocompta.fr/comptabilite/frais-de-port
				return "SAA", "Shipping and handling"
