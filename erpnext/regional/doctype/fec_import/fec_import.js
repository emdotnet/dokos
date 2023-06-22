// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('FEC Import', {
	refresh(frm) {
		frm.get_field("fec_file").df.options = {
			restrictions: {
				allowed_file_types: [".txt", ".csv"],
			},
		};

		frm.trigger("add_description");
		frm.trigger("add_actions");
	},

	add_actions(frm) {
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

			frm.add_custom_button(__("View Accounts"), function() {
				frappe.set_route("Tree", "Account")
			}, __("View"));

			frm.add_custom_button(__("View Journals"), function() {
				frappe.set_route("List", "Accounting Journal")
			}, __("View"));
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

	add_description(frm) {
		let description = __("1. Import your FEC file")
		if (!frm.is_new()) {
			description += "</br>"
			description += __("2. Import your accounts.")
			description += "</br>"
			description += "<i>"
			description += __("This operation will not erase your existing accounts. Dokos will try to append them to their corresponding parents in the tree.")
			description += "</i>"
			description += "</br>"
			description += __("3. Configure your accounts properly by adding the correct account type, especially for receivable and payable accounts (Classe 4).")
			description += "</br>"
			description += __("4. Import your accounting journals.")
			description += "</br>"
			description += "<i>"
			description += __("This operation will not erase your existing accounting journals.")
			description += "</i>"

			description += "</br>"
			description += __("5. Configure your journals properly, especially the Bank and Cash journals.")
		}

		description += "</br>"

		frm.get_field("description").$wrapper.html(description)
		frm.get_field("description").$wrapper.addClass("mb-4")
	}
});
