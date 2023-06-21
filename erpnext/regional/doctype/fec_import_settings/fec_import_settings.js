// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('FEC Import Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__("Import a FEC"), () => {
			frappe.new_doc('FEC Import', {company: frm.doc.company});
		})
	}
});
