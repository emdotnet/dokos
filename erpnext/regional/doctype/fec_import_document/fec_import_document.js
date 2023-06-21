// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('FEC Import Document', {
	refresh: function(frm) {
		if (frm.doc.status != "Completed") {
			frm.add_custom_button(`${__("Retry an integration")}`, () => {
				frappe.call({
					method: "create_linked_document",
					doc: frm.doc
				}).then(r => {
					frappe.show_alert({
						message: __("Retry in progress"),
						indicator: "orange"
					})

					frm.refresh()
				})
			});
		}
	}
});
