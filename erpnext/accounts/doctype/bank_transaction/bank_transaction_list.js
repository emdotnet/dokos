// Copyright (c) 2019, Dokos SAS and Contributors
// License: See license.txt
frappe.provide("erpnext.accounts");

frappe.listview_settings['Bank Transaction'] = {
	add_fields: ["unallocated_amount"],
	hide_name_column: 1,
	get_indicator: function(doc) {
		if (doc.status === "Unreconciled") {
			return [__("Unreconciled", null, "Bank Transaction"), "orange", "status,=,Unreconciled"];
		} else if (doc.status === "Reconciled") {
			return [__("Reconciled", null, "Bank Transaction"), "green", "status,=,Reconciled"];
		} else if (doc.status === "Closed") {
			return [__("Closed"), "darkgray", "status,=,Closed"];
		} else if (doc.status === "Pending") {
			return [__("Closed"), "blue", "status,=,Pending"];
		} else if (doc.status === "Settled") {
			return [__("Closed"), "green", "status,=,Settled"];
		}
	},
	onload: function(list_view) {
		frappe.require('bank-transaction-importer.bundle.js', function() {
			frappe.db.get_value("Plaid Settings", "Plaid Settings", "enabled", (r) => {
				if (r && r.enabled == "1") {
					list_view.page.add_menu_item(__("Synchronize this account"), function() {
						new erpnext.accounts.bankTransactionUpload('plaid');
					});
				}
			})
			list_view.page.add_menu_item(__("Upload an ofx statement"), function() {
				new erpnext.accounts.bankTransactionUpload('ofx');
			});
			list_view.page.add_menu_item(__("Upload a csv/xlsx statement"), function() {
				new erpnext.accounts.bankTransactionUpload('csv');
			});
		});
	},
	on_update: function(list_view) {
		list_view.refresh()
	},
	button: {
		show: () => {
			return frappe.perm.has_perm("Bank Transaction", 0, 'write');
		},
		get_description: () => {
			return __("Select a category")
		},
		get_label: () => {
			return __("Action", null, "Bank Transaction")
		},
		action: (doc) => {
			const d = new frappe.ui.Dialog({
				title: __("Select a category"),
				fields: [
					{
						label : __("Category"),
						fieldname: "category",
						fieldtype: "Link",
						reqd: 1,
						options: "Bank Transaction Category",
						default: doc.category
					},
				],
				primary_action: () => {
					frappe.db.set_value("Bank Transaction", doc.name, "category", d.get_value("category"));
					d.hide();
				}
			});
			d.show();
		}
	}
};
