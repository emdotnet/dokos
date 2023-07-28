import frappe


def get_context(context):
	# do your magic here
	context.show_sidebar = True

	if not frappe.form_dict.is_list:
		context.template = "erpnext/utilities/web_form/addresses/addresses.html"
