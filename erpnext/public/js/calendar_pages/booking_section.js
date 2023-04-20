// Copyright (c) 2023, Dokos SAS and Contributors
// See license.txt

import EventEmitterMixin from 'frappe/public/js/frappe/event_emitter';

import './base_calendar';

frappe.provide("erpnext.booking_section");
frappe.provide("erpnext.booking_section_update")

erpnext.booking_section_update = {}

erpnext.booking_section = class BookingDialog {
	constructor(opts) {
		Object.assign(this, opts);
		Object.assign(erpnext.booking_section_update, EventEmitterMixin);

		this.skip_cart = this.skip_cart == "True";
		this.read_only = frappe.session.user === "Guest";
		this.wrapper = document.getElementsByClassName(this.parentId)[0];

		this.build_calendar();
	}

	build_calendar() {
		this.booking_calendar = new BookingCalendar({
			wrapper: this.wrapper,
			booking_dialog: this,
		})

		erpnext.booking_section_update.on("update_calendar", r => {
			this.uom = r;
			this.booking_calendar.booking_selector?.empty();
			this.booking_calendar?.refetchEvents();
		})
	}

	destroy_calendar() {
		this.booking_calendar.destroy();
	}
}

class BookingCalendar extends frappe.ui.BaseWebCalendar {
	init() {
		this.slots = [];
		this.booking_dialog = this.options.booking_dialog;
	}

	async getEvents(parameters) {
		const result = await frappe.call("erpnext.templates.pages.cart.get_availabilities_for_cart", {
			start: this.format_ymd(parameters.start),
			end: this.format_ymd(parameters.end),
			item: this.booking_dialog.item,
			uom: this.booking_dialog.uom
		});

		this.slots = result.message;

		const date = this.booking_dialog.date
		if (date && !this.booking_selector) {
			this._make_booking_selector({ date });
		} else {
			this.booking_selector?.make();
		}

		return this.slots;
	}

	get_header_toolbar() {
		return {
			left: '',
			center: 'prev,title,next',
			right: 'today',
		}
	}

	_make_booking_selector(date_info) {
		this.booking_selector = new BookingSelector({
			booking_calendar: this,
			booking_dialog: this.booking_dialog,
			date_info: date_info,
		});
	}

	onDateClick(info) {
		this._make_booking_selector(info);
	}

	onDatesSet(info) {
		this.booking_selector?.empty();
	}

	calendar_options() {
		let initialDate;
		const queryParamStartDate = new URLSearchParams(window.location.search).get("start_date");
		if (this.booking_dialog.date) {
			initialDate = this.format_ymd(this.booking_dialog.date);
		} else if (queryParamStartDate) {
			initialDate = queryParamStartDate;
		} else {
			initialDate = momentjs().add(1,'d').format("YYYY-MM-DD");
		}

		return Object.assign(super.calendar_options(), {
			initialDate,
			noEventsContent: __("No slot available"),
			eventClassNames(arg) {
				return ["booking-calendar", arg.event.extendedProps.status || ""]
			},
		});
	}
}

class BookingSelector {
	constructor(opts) {
		Object.assign(this, opts);
		this.credits = 0.0;
		this.make()
	}

	make() {
		frappe.call({
			method: "erpnext.venue.doctype.booking_credit.booking_credit.get_booking_credits_by_item",
			args: {
				item: this.booking_dialog.item,
				uom: this.booking_dialog.uom
			}
		}).then(r => {
			if (r.message) {
				this.credits = r.message;
			}
			this.slots = this.booking_calendar.slots.filter(s => (
				frappe.datetime.get_date(s.start) <= frappe.datetime.get_date(this.date_info.date)
				) && (
					frappe.datetime.get_date(this.date_info.date) <= frappe.datetime.get_date(s.end)
				)
			)

			this.build();
			this.render();
		})
	}

	build() {
		const me = this;
		const locale = this.booking_calendar.locale;

		/** @type {Date | null} */
		const date = this.date_info.date;

		const slots_div = this.slots.length ? this.slots.sort((a,b) => new Date(a.start) - new Date(b.start)).map(s => {
			const number_indicator = s.number > 0 ? `<div class="cart-indicator list-indicator ml-0">${s.number}</div>` : ""

			return `<div class="timeslot-options mb-4 px-4" data-slot-id="${s.id}">
				<button class="btn btn-outline-secondary ${s.status}" type="button">
					<div class="d-flex justify-content-center">
						<div class="mx-auto">
							${momentjs(s.start).locale(locale).format('LT')} - ${momentjs(s.end).locale(locale).format('LT')}
						</div>
						${number_indicator}
					</div>
				</button>
			</div>`
		}): [];

		this.$content = $(`<div>
			<h2 class="timeslot-options-title text-muted mb-4">${date ? momentjs(date).locale(locale).format('LL') : ""}</h2>
			${slots_div.join('')}
		</div>`)

		this.$content.find('.timeslot-options').on('click', function() {
			const selected_slot = me.slots.filter(f => f.id == $(this).attr("data-slot-id"));
			me.select_slot(selected_slot)
		})

	}

	empty() {
		$(".booking-selector").empty()
	}

	render() {
		this.empty()
		$(".booking-selector").append(this.$content)
	}

	select_slot(selected_slot) {
		if (selected_slot.length) {
			selected_slot = selected_slot[0]

			if (frappe.session.user == "Guest") {
				return window.location = `/login?redirect-to=${window.location.pathname}?date=${selected_slot.start}`
			}

			if (selected_slot.status == "selected") {
				this.remove_booked_slot(selected_slot.id)
			} else {
				if (this.credits > 0) {
					const d = new frappe.ui.Dialog({
						title: __("Use your credits"),
						size: "large",
						fields: [
							{
								"fieldtype": "HTML",
								"fieldname": "content",
							}
						],
						primary_action_label: __("Use my credits"),
						primary_action: () => {
							this.book_new_slot(selected_slot, true)
							d.hide()
						},
						secondary_action_label: __("Do not use my credits"),
						secondary_action: () => {
							this.book_new_slot(selected_slot)
							d.hide()
						}
					})
					d.fields_dict.content.$wrapper.html(
						`
							<div>
								<h6>${__("You have") + " " + this.credits + " " + (this.credits > 1 ? __("credits") : __("credit")) + " " + __("available for this resource.")}</h6>
								<h6>${__("Do you want to use your credits for this booking ?")}</h6>
							</div>
						`
					);
					d.show();
				} else {
					this.book_new_slot(selected_slot)
				}
			}
		}
	}

	book_new_slot(event, with_credits) {
		frappe.call("erpnext.venue.doctype.item_booking.item_booking.book_new_slot", {
			start: moment.utc(event.start).format("YYYY-MM-DD H:mm:SS"),
			end: moment.utc(event.end).format("YYYY-MM-DD H:mm:SS"),
			item: this.booking_dialog.item,
			uom: this.booking_dialog.uom,
			user: frappe.session.user,
			status: this.booking_dialog.skip_cart ? "Confirmed": null,
			with_credits: with_credits
		}).then(r => {
			console.log(r)
			if (!this.booking_dialog.skip_cart) {
				this.update_cart(r.message.name, 1)
			} else {
				this.booking_calendar?.refetchEvents();
			}
		})
	}

	remove_booked_slot(booking_id) {
		if (!this.booking_dialog.skip_cart) {
			this.update_cart(booking_id, 0)
		} else {
			frappe.call("erpnext.venue.doctype.item_booking.item_booking.remove_booked_slot", {
				name: booking_id
			}).then(r => {
				this.booking_calendar?.refetchEvents();
			})
		}
	}

	update_cart(booking, qty) {
		erpnext.e_commerce.shopping_cart.shopping_cart_update({
			item_code: this.booking_dialog.item,
			qty: qty,
			uom: this.booking_dialog.uom,
			booking: booking,
			cart_dropdown: true,
		}).then(() => {
			this.booking_calendar?.refetchEvents();
		})
	}
}
