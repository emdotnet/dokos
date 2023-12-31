// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subscription', {
	setup: function(frm) {
		frm.trigger('setup_listeners');

		frm.set_indicator_formatter('item', function(doc) {
			return (doc.status == "Active") ? "green" : (doc.status == "Upcoming") ? "orange" : "darkgray";
		});

		frm.make_methods = {
			'Payment Request': () => {
				frm.events.create_payment_request(frm);
			},
			'Payment Entry': () => {
				frm.events.create_payment(frm);
			}
		}

		frappe.dynamic_link = {doc: frm.doc, fieldname: 'customer', doctype: 'Customer'}
		frm.set_query('contact_person', erpnext.queries.contact_query)

		frm.set_query('print_format', function() {
			return {
				filters: {
					"doc_type": "Sales Invoice",
					"disabled": 0
				}
			}
		});
	},
	refresh: function(frm) {
		frm.page.clear_actions_menu();
		if(!frm.is_new()){
			if(frm.doc.status !== 'Cancelled'){
				if(!frm.doc.cancellation_date){
					frm.page.add_action_item(
						__('Stop Subscription'),
						() => frm.events.cancel_this_subscription(frm)
					);
					frm.page.add_action_item(
						__('Link a sales invoice'),
						() => frm.events.link_sales_invoice(frm)
					);
				} else {
					frm.page.add_action_item(
						__('Do not cancel this subscription'),
						() => frm.events.abort_cancel_this_subscription(frm)
					);
				}
				frm.add_custom_button(
					__('Fetch Subscription Updates'),
					() => frm.events.get_subscription_updates(frm)
				);

			}
			else if(frm.doc.status === 'Cancelled'){
				frm.page.add_action_item(
					__('Restart Subscription'),
					() => frm.events.renew_this_subscription(frm)
				);
			}

			frappe.xcall("erpnext.accounts.doctype.subscription.subscription.subscription_headline", {
				'name': frm.doc.name
			})
			.then(r => {
				frm.dashboard.clear_headline();
				frm.dashboard.set_headline_alert(r);
			})
		}
		frm.set_value("company", frappe.defaults.get_user_default("Company"));
		frm.trigger("show_stripe_section");

		if (frm.is_new() && !frm.doc.print_format) {
			frappe.model.with_doctype("Sales Invoice", function() {
				frm.set_value("print_format", frappe.get_meta("Sales Invoice").default_print_format)
			});
		}
	},

	customer: function(frm) {
		if (frm.doc.customer) {
			frappe.xcall("erpnext.accounts.party.get_default_contact", {
				doctype: "Customer",
				name: frm.doc.customer
			}).then(r => {
				frm.set_value("contact_person", r)
			})
		}
	},

	cancel_this_subscription: function(frm) {
		let fields = [
			{
				"fieldtype": "Date",
				"label": __("Cancellation date"),
				"fieldname": "cancellation_date",
				"default": frm.doc.current_invoice_end
			},
			{
				"fieldtype": "Check",
				"label": __("Prorate last invoice"),
				"fieldname": "prorate_last_invoice"
			}
		]

		const dialog = new frappe.ui.Dialog({
			title: __("Cancel subscription"),
			fields: fields,
			primary_action: function() {
				const values = dialog.get_values();
				values["name"] = frm.doc.name
				dialog.hide()
				frappe.call({
					method:
					"erpnext.accounts.doctype.subscription.subscription.cancel_subscription",
					args: values,
					callback: function(data){
						if(!data.exc){
							frm.reload_doc();
						}
					}
				});
			}
		})
		dialog.show()
	},

	link_sales_invoice: function(frm) {
		frappe.prompt({
			fieldtype: 'Link',
			label: __('Select a sales invoice'),
			fieldname: 'sales_invoice',
			reqd: 1,
			options: 'Sales Invoice',
			get_query: function() {
				return {
					"filters": {
						"subscription": ["is", "not set"],
						"docstatus": 1
					}
				}
			}
		}, data => {
			frappe.call({
				method: "link_sales_invoice",
				doc: frm.doc,
				args: data
			}).then(r => {
				console.log(r)
				frappe.show_alert({
					message: __("The selected sales invoice has been linked to this subscription"),
					indicator: "green"
				})
			})
		}, __("Select a sales invoice to link to this subscription"), __("Confirm"));
	},

	abort_cancel_this_subscription: function(frm) {
		frappe.call({
			method:
			"erpnext.accounts.doctype.subscription.subscription.restart_subscription",
			args: {
				name: frm.doc.name
			},
			callback: function(data){
				if(!data.exc){
					frm.reload_doc();
				}
			}
		});
	},

	renew_this_subscription: function(frm) {
		const doc = frm.doc;
		frappe.confirm(
			__('Are you sure you want to restart this subscription?'),
			function() {
				frappe.call({
					method:
					"erpnext.accounts.doctype.subscription.subscription.restart_subscription",
					args: {name: doc.name},
					callback: function(data){
						if(!data.exc){
							frm.reload_doc();
						}
					}
				});
			}
		);
	},

	get_subscription_updates: function(frm) {
		const doc = frm.doc;
		frappe.show_alert({message: __("Subscription update in progress"), indicator: "orange"})
		frappe.call({
			method:
			"erpnext.accounts.doctype.subscription.subscription.get_subscription_updates",
			args: {name: doc.name}
		}).then(r => {
			if(!r.exc){
				frm.reload_doc();
				frappe.show_alert({message: __("Subscription up to date"), indicator: "green"})
			} else {
				frappe.show_alert({message: __("Subscription update failed. Please try again or check the error log."), indicator: "red"})
			}
		});
	},

	setup_listeners: function(frm) {
		frappe.realtime.on('payment_gateway_updated', (data) => {
			const format_values = value => {
				return format_currency(value / 100, frm.doc.currency)
			}
			if (data.initial_amount && data.updated_amount) {
				frappe.show_alert({message: __("Payment gateway subscription amount updated from {0} to {1}",
					[format_values(data.initial_amount), format_values(data.updated_amount)]), indicator: 'green'})
			}
		})
	},
	create_payment(frm) {
		return frappe.call({
			method: "erpnext.accounts.doctype.subscription.subscription.get_payment_entry",
			args: {
				"name": frm.doc.name
			}
		}).then(r => {
			const doclist = frappe.model.sync(r.message);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		});
	},
	create_payment_request(frm) {
		return frappe.call({
			method: "erpnext.accounts.doctype.subscription.subscription.get_payment_request",
			args: {
				"name": frm.doc.name
			}
		}).then(r => {
			const doclist = frappe.model.sync(r.message);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		});
	},
	subscription_plan(frm) {
		if (frm.doc.subscription_plan) {
			frappe.xcall("erpnext.accounts.doctype.subscription.subscription.get_subscription_plan", {
				plan: frm.doc.subscription_plan
			}).then(r => {
				if (frm.is_new() && frm.doc.plans.length) {
					frm.doc.plans = frm.doc.plans.map(f => f.item).filter(f => f != undefined)
				}

				r.forEach(values => {
					const row = frappe.model.add_child(frm.doc, "Subscription Plan Detail", "plans");
					Object.keys(values).forEach(v => {
						frappe.model.set_value(row.doctype, row.name, v, values[v])
					})
				})
				frm.refresh_field("plans");
			})
		}
	},
	modify_current_invoicing_end_date(frm) {
		frappe.prompt({
			fieldtype: 'Date',
			label: __('New Current Invoice End Date'),
			fieldname: 'end_date',
			reqd: 1,
			default: frm.doc.current_invoice_end
		}, data => {
				frappe.xcall("erpnext.accounts.doctype.subscription.subscription.new_invoice_end", {
					subscription: frm.doc.name,
					end_date: data.end_date
				}).then(() => {
					frm.reload_doc();
				})
		}, __("Set a new date"), __("Submit"));
	}
});

frappe.ui.form.on('Subscription Plan Detail', {
	item: function(frm, cdt, cdn) {
		const row = locals[cdt][cdn]
		frappe.model.with_doc("Item", row.item, function() {
			const item = frappe.get_doc("Item", row.item)
			item.description&&frappe.model.set_value(cdt, cdn, "description", item.description);
			const uom = item.sales_uom ? item.sales_uom : item.stock_uom;
			frappe.model.set_value(cdt, cdn, "uom", uom);
		});
	},
	add_invoice_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn]
		if (!row.stripe_invoice_item) {
			frappe.call({
				method: "create_stripe_invoice_item",
				doc: frm.doc,
				args: {
					"plan_details": row
				}
			}).then(r => {
				if (r && r.message) {
					frappe.model.set_value(cdt, cdn, "stripe_invoice_item", r.message.id);
					frappe.show_alert({
						message: __("Invoice item created."),
						color: "green"
					})
				}
			})
		} else {
			frappe.throw(__("This plan is already linked to an invoice item."))
		}
	}
})
