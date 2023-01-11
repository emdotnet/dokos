# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt


import frappe

## Custom fields for multi company
def get_custom_fields():
	def _get_fields(insert_after: str):
		# hint for translation
		# frappe._('Show only for selected companies')
		# frappe._('Multi Company')

		return [{
			'insert_after': insert_after,
			'fieldname': '_section_break_multicompany',
			'fieldtype': 'Section Break',
			'label': 'Multi Company',
			'collapsible': 0,
		}, {
			'insert_after': '_section_break_multicompany',
			'fieldname': 'only_companies',
			'fieldtype': 'Table MultiSelect',
			'label': 'Show only for selected companies',
			'options': 'Venue Selected Company',
		}, {
			'insert_after': 'only_companies',
			'fieldname': 'btn_only_companies_reset',
			'fieldtype': 'Button',
			'label': 'Reset to defaults',
		}]
	return {
		'Item Group': _get_fields(insert_after='website_specifications'),
		'Website Item': _get_fields(insert_after='brand'),
	}

def multicompany_create_custom_fields(venue_settings):
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	custom_fields = get_custom_fields()
	create_custom_fields(custom_fields)

	companies = [c.company for c in venue_settings.cart_settings_overrides]

	for doctype, fields in custom_fields.items():
		for df in fields:
			if df['fieldname'] == 'only_companies':
				docs_to_update = frappe.get_all(doctype)
				for doc in docs_to_update:
					doc = frappe.get_doc(doctype, doc.name)
					if not doc.only_companies:
						for company in companies:
							doc.append('only_companies', {'company': company})
						doc.save()

def multicompany_delete_custom_fields(venue_settings):
	custom_fields = get_custom_fields()
	for doctype, fields in custom_fields.items():
		for df in fields:
			docname = frappe.db.get_value('Custom Field', {
				'dt': doctype,
				'fieldname': df['fieldname']
			})

			if docname:
				frappe.delete_doc('Custom Field', docname)
