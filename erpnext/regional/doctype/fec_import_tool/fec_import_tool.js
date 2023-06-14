// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('FEC Import Tool', {
	refresh(frm) {
		frm.get_field("fec_file").df.options = {
			restrictions: {
				allowed_file_types: [".txt"],
			},
		};

		if (frm.doc.fec_file) {
			frm.page.set_primary_action(__("Import FEC"), function() {
				frappe.call({
					method: "upload_fec",
					doc: frm.doc,
				}).then(r => {
					frappe.show_alert({
						message: __("Import in progress"),
						indicator: "green"
					})
				})
			});

			frm.add_custom_button(__("Create Journals"), function() {
				frappe.call({
					method: "create_journals",
					doc: frm.doc,
				}).then(r => {
					frappe.show_alert({
						message: __("Accounting journals created.<br>Please setup a correct journal type for each."),
						indicator: "green"
					})
				})
			}, __("Actions"));

			frm.add_custom_button(__("Create Accounts"), function() {
				frappe.call({
					method: "create_accounts",
					doc: frm.doc,
				}).then(r => {
					frappe.show_alert({
						message: __("Accounts created.<br>Please setup a correct account type for each."),
						indicator: "green"
					})
				})
			}, __("Actions"));
		}

	},
	fec_file(frm) {
		if (frm.doc.fec_file) {
			frm.call({
				method: "get_company",
				doc: frm.doc,
			}).then(r => {
				frm.set_value("company", r.message)
			})
		}
	},
});
