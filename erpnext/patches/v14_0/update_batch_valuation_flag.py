import frappe


def execute():
	"""
	- Don't use batchwise valuation for existing batches.
	- Only batches created after this patch shoule use it.
	"""
	frappe.db.sql("""
		UPDATE `tabBatch`
		SET use_batchwise_valuation=0
	""")
