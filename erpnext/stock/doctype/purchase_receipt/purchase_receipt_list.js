frappe.listview_settings['Purchase Receipt'] = {
	add_fields: ["supplier", "supplier_name", "base_grand_total", "is_subcontracted",
		"transporter_name", "is_return", "status", "per_billed", "currency"],
	get_indicator: function(doc) {
		if(cint(doc.is_return)==1) {
			return [__("Return"), "darkgray", "is_return,=,Yes"];
		} else if (doc.status === "Closed") {
			return [__("Closed"), "green", "status,=,Closed"];
		} else if (flt(doc.grand_total) !== 0 && flt(doc.per_billed, 2) < 100) {
			return [__("To Bill"), "orange", "per_billed,<,100"];
		} else if (flt(doc.grand_total) === 0 || flt(doc.per_billed, 2) == 100) {
			return [__("Completed"), "green", "per_billed,=,100"];
		}
	},
	onload: function(list_view) {
		frappe.require("assets/erpnext/js/accounting_journal_adjustment.js", () => {
			list_view.page.add_actions_menu_item(
				__("Accounting Journal Adjustment"),
				() => {
					const docnames = list_view.get_checked_items(true);
					new erpnext.journalAdjustment({doctype: list_view.doctype, docnames: docnames})
				},
				true
			);
		});
	}
};
