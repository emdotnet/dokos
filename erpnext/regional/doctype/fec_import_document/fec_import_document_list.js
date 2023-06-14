frappe.listview_settings["FEC Import Document"] = {
	onload: function (doclist) {
		const action = () => {
			const selected_docs = doclist.get_checked_items();
			if (selected_docs.length > 0) {
				let docnames = selected_docs.map((doc) => doc.name);
				frappe.call({
					method: "erpnext.regional.doctype.fec_import_document.fec_import_document.bulk_process",
					args: { docnames },
				}).then(() => {
					frappe.show_alert({
						message: __("Bulk processing in progress"),
						indicator: "orange"
					})
				})
			}
		};
		doclist.page.add_actions_menu_item(__("Bulk Process"), action, false);
	},
};
