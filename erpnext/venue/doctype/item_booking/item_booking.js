// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Booking', {
	onload(frm) {
		frappe.realtime.off("booking_overlap");
		frappe.realtime.on("booking_overlap", () => {
			frappe.show_alert({
				message: __("This item booking is overlapping with another item booking for the same item"),
				indicator: "orange"
			})
		})
	},
	setup(frm) {
		frappe.realtime.off("event_synced");
		frappe.realtime.on('event_synced', (data) => {
			frappe.show_alert({message: data.message, indicator: 'green'});
			frm.reload_doc();
		})

		frm.make_methods = {
			'Quotation': () => {
				make_quotation(frm)
			},
			'Sales Order': () => {
				make_sales_order(frm)
			},
			'Booking Credit Usage': () => {
				make_booking_credit_usage(frm)
			}
		}
	},
	refresh(frm) {
		if (frm.doc.parent_item_booking) {
			frm.trigger("disable_form");
		} else {
			frm.page.clear_actions_menu();
			frm.page.add_action_item(__("Create a quotation"), () => {
				make_quotation(frm)
			})

			frm.trigger('add_to_quotation');
			frm.trigger('add_to_sales_order');
		}

		frm.set_query('party_type', () => {
			return {
				filters: {
					name: ['in', ['Lead', 'Customer']]
				}
			};
		});

		frm.set_query('sales_uom', () => {
			return {
				query:"erpnext.accounts.doctype.pricing_rule.pricing_rule.get_item_uoms",
				filters: {'value': frm.doc.item, apply_on: 'Item Code'}
			}
		})

		frm.set_query("user", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					ignore_user_type: 1
				}
			}
		});

		frm.set_query('google_calendar', function() {
			return {
				filters: {
					"reference_document": "Item Booking"
				}
			};
		});

		if (frm.delayInfo) {
			clearInterval(frm.delayInfo)
		}

		if (!frm.is_new() && frm.doc.status === "In cart") {
			frm.trigger('set_cart_countdown');
		} else {
			frm.trigger('get_booking_count');
		}

		frm.trigger('add_repeat_text');
	},
	set_cart_countdown(frm) {
		frappe.db.get_single_value("Venue Settings", "clear_item_booking_draft_duration")
		.then(r => {
			frm.delayInfo && clearInterval(frm.delayInfo);

			if (r && r>0 && !frm.delayInfo) {
				frm.delayInfo = setInterval( () => {
					const delay = frappe.datetime.get_minute_diff(
						frappe.datetime.add_minutes(frm.doc.modified || frappe.datetime.now_datetime(), r),
						frappe.datetime.now_datetime())
					frm.set_intro()
					if (delay > 0) {
						frm.set_intro(__("This document will be automatically deleted in {0} minutes if not validated.", [delay]))
					}
				}, 10000 )
			}
		} )
	},
	add_repeat_text(frm) {
		if (frm.doc.rrule) {
			new frappe.CalendarRecurrence({frm: frm, show: false});
		}
	},
	sync_with_google_calendar(frm) {
		frm.trigger('get_google_calendar_and_color');
	},
	item(frm) {
		frm.trigger('get_booking_count')
		frm.trigger('get_google_calendar_and_color');
	},
	get_google_calendar_and_color(frm) {
		if (frm.doc.item) {
			frappe.db.get_value("Item", frm.doc.item, ["google_calendar", "calendar_color"], r => {
				if (r) {
					r.google_calendar&&frm.set_value("google_calendar", r.google_calendar);
					r.calendar_color&&frm.set_value("color", r.calendar_color);
				}
			})
		}
	},
	repeat_this_event(frm) {
		if(frm.doc.repeat_this_event === 1) {
			new frappe.CalendarRecurrence({frm: frm, show: true});
		}
	},
	add_to_quotation(frm) {
		frm.page.add_action_item(__("Add to an existing quotation"), () => {
			add_to_transaction(frm, "Quotation")
		})
	},
	add_to_sales_order(frm) {
		frm.page.add_action_item(__("Add to an existing sales order"), () => {
			add_to_transaction(frm, "Sales Order")
		})
	},
	user(frm) {
		if (frm.doc.user) {
			frappe.xcall("erpnext.venue.doctype.item_booking.item_booking.get_corresponding_party", {
				user: frm.doc.user
			}).then(r => {
				if (r&&r.length) {
					frm.set_value("party_type", r[0]);
					frm.set_value("party_name", r[1]);
				}
			})
		}
	},
	disable_form: function(frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
	get_booking_count: function(frm) {
		frappe.xcall("erpnext.venue.doctype.item_booking.item_booking.get_booking_count", {
			item: frm.doc.item,
			starts_on: frm.doc.starts_on,
			ends_on: frm.doc.ends_on,
		}).then(r => {
			if (r) {
				let message = __("{0} slots are still available for this item and this time slot.", [r])
				if (r < 2) {
					message = __("{0} slot still available for this item and this time slot.", [r])
				}
				frm.set_intro()
				frm.set_intro(message)
			}
		});
	},
	starts_on: function(frm) {
		frm.trigger('get_booking_count')
	},
	ends_on: function(frm) {
		frm.trigger('get_booking_count')
	},
});

const add_to_transaction = (frm, transaction_type) => {
	const d = new frappe.ui.form.MultiSelectDialog({
		doctype: transaction_type,
		target: "Item Booking",
		date_field: "transaction_date" || undefined,
		setters: transaction_type === "Quotation" ? {"party_name": ""} : {"customer": ""},
		get_query: () => {
			return {
				filters: {
					docstatus: ["!=", 2]
				}
			}
		},
		action: function(selections, args) {
			const values = selections;
			if(values.length === 0){
				frappe.msgprint(__("Please select a {0}", [__(transaction_type)]))
				return;
			}
			d.dialog.hide();
			new ItemSelector({values: values, frm: frm, transaction_type: transaction_type})
		},
	});
}

class ItemSelector {
	constructor(opts) {
		Object.assign(this, opts)
		this.make()
	}

	make() {
		this.get_data()
		.then(r => {
			this.items = r.filter(f => !f.item_booking);
			this.make_dialog();
		})
	}

	get_data() {
		return frappe.xcall("erpnext.venue.doctype.item_booking.item_booking.get_transactions_items", {
			transaction_type: this.transaction_type,
			transactions: this.values
		})
	}

	make_dialog() {
		const me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Select an item"),
			fields: [{ fieldtype: "HTML", fieldname: "items_area" }],
			primary_action_label: __("Select"),
			primary_action: () => {
				const value = this.get_checked_values()
				if (value.length) {
					frappe.xcall("erpnext.venue.doctype.item_booking.item_booking.update_linked_transaction", {
						transaction_type: this.transaction_type,
						line_item: value[0],
						item_booking: this.frm.doc.name
					}).then(r => {
						if (!r) {
							frappe.show_alert({
								message: __("The quotation has been updated", [__(me.transaction_type).toLowerCase()]),
								indicator: "green"
							})
							this.frm.reload_doc();
						}
					})
				}
				this.dialog.hide();
			}
		});
		this.$parent = $(this.dialog.body);
		this.$wrapper = this.dialog.fields_dict.items_area.$wrapper.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);

		this.$items = this.$wrapper.find('.results');
		this.$items.append(this.make_list_row());
		this.render_result_list();
		this.bind_events();
		this.dialog.show()
	}

	make_list_row(result={}) {
		const me = this;
		const head = Object.keys(result).length === 0;

		let contents = ``;
		let columns = ["parent", "item_code", "qty", "uom"];

		columns.forEach(function(column) {
			contents += `<div class="list-item__content ellipsis">
				${
					head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`

					: (column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
						: `<a href="${"/app/Form/"+ me.doctype + "/" + result[column]}" class="list-id ellipsis">
							${__(result[column])}</a>`)
				}
			</div>`;
		})

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				${head ? '' : `<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${result.checked ? 'checked' : ''}>`}
			</div>
			${contents}
		</div>`);

		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);
		return $row;
	}

	get_checked_values() {
		// Return name of checked value.
		return this.$items.find('.list-item-container').map(function() {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
				return $(this).attr('data-item-name');
			}
		}).get();
	}

	render_result_list() {
		const me = this;
		let checked = this.get_checked_values();

		this.items
			.filter(result => !checked.includes(result.name))
			.forEach(result => {
				me.$items.append(me.make_list_row(result));
			});

		if (frappe.flags.auto_scroll) {
			this.$items.animate({scrollTop: me.$items.prop('scrollHeight')}, 500);
		}
	}

	bind_events() {
		const me = this;
		this.$items.on('click', '.list-item-container', function (e) {
			if (!$(e.target).is(':checkbox') && !$(e.target).is('a')) {
				me.$items.find(':checkbox').prop("checked", false);
				$(this).find(':checkbox').trigger('click');
			}
		});
	}

}

const make_quotation = frm => {
	frappe.xcall(
		"erpnext.venue.doctype.item_booking.item_booking.make_quotation",
		{ source_name: frm.doc.name }
	).then(r => {
		if (r) {
			const doclist = frappe.model.sync(r);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		}
	})
}

const make_sales_order = frm => {
	frappe.xcall(
		"erpnext.venue.doctype.item_booking.item_booking.make_sales_order",
		{ source_name: frm.doc.name }
	).then(r => {
		if (r) {
			const doclist = frappe.model.sync(r);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		}
	})
}

const make_booking_credit_usage = frm => {
	frappe.xcall(
		"erpnext.venue.doctype.item_booking.item_booking.make_booking_credit_usage",
		{ source_name: frm.doc.name }
	).then(r => {
		if (r) {
			const doclist = frappe.model.sync(r);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		}
	})
}

frappe.tour['Item Booking'] = [
	{
		fieldname: "item",
		title: __("Item"),
		description: __("Item booked by the user. This item will also be used to invoice the customer.")
	},
	{
		fieldname: "user",
		title: __("User"),
		description: __("User linked with this booking.")
	},
	{
		fieldname: "color",
		title: __("Color"),
		description: __("By default the color set in the item master data. Used to visualize the booking in your calendar.")
	},
	{
		fieldname: "status",
		title: __("Status"),
		description: __("Status of the booking. If the status is cancelled, the slot will remain available, else it will be considered as unavailable.")
	},
	{
		fieldname: "starts_on",
		title: __("Starts on"),
		description: __("Booked slot start time.")
	},
	{
		fieldname: "ends_on",
		title: __("Ends on"),
		description: __("Booked slot end time.")
	},
	{
		fieldname: "all_day",
		title: __("All day"),
		description: __("Check this field if your event is an all day event.")
	},
	{
		fieldname: "repeat_this_event",
		title: __("Repeat this event"),
		description: __("Check this field and configure the repeat options if your event is a recurring event.")
	},
	{
		fieldname: "sync_with_google_calendar",
		title: __("Sync with Google Calendar"),
		description: __("Check this field if you want to synchronize your event with Google Calendar. Make sure your Google Calendar integration is setup and you have created at least one calendar.")
	},
	{
		fieldname: "notes",
		title: __("Notes"),
		description: __("This field allows you to register notes linked to this booking. Users can also add notes when booking on the website.")
	},
	{
		fieldname: "party_type",
		title: __("Party type"),
		description: __("Allows you to link this item booking with a customer or a lead. Used to select the appropriate party.")
	},
	{
		fieldname: "party_name",
		title: __("Party name"),
		description: __("Name of the party linked to this booking. Used to create the quotation.")
	}
]
