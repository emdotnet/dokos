// Copyright (c) 2023, Dokos SAS and Contributors
// See license.txt

import { Calendar } from '@fullcalendar/core';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import dayGridPlugin from '@fullcalendar/daygrid';
import EventEmitterMixin from 'frappe/public/js/frappe/event_emitter';

frappe.provide("erpnext.booking_section");
frappe.provide("erpnext.booking_section_update")

erpnext.booking_section_update = {}

erpnext.booking_section = class BookingDialog {
	constructor(opts) {
		Object.assign(this, opts);
		Object.assign(erpnext.booking_section_update, EventEmitterMixin);

		this.read_only = frappe.session.user === "Guest";
		this.wrapper = document.getElementsByClassName(this.parentId)[0];

		this.build_calendar();
	}

	build_calendar() {
		this.calendar = new BookingCalendar(this)

		erpnext.booking_section_update.on("update_calendar", r => {
			this.uom = r;
			this.calendar.booking_selector&&this.calendar.booking_selector.empty();
			this.calendar.fullCalendar&&this.calendar.fullCalendar.refetchEvents();
		})
	}

	destroy_calendar() {
		this.calendar.destroy();
	}
}

class BookingCalendar {
	constructor(parent) {
		this.parent = parent;
		this.slots = [];
		this.booking_selector = null;
		this.locale = frappe.get_cookie('preferred_language') || frappe.boot.lang || 'en';
		this.skip_cart = this.parent.skip_cart == "True"
		this.render();
	}

	render() {
		$(this.parent.wrapper).empty()
		const calendarEl = $('<div></div>').appendTo($(this.parent.wrapper));
		this.fullCalendar = new Calendar(
			calendarEl[0],
			this.calendar_options()
		)
		this.fullCalendar.render();
	}

	get_header_toolbar() {
		return {
			left: '',
			center: 'prev,title,next',
			right: 'today',
		}
	}

	set_option(option, value) {
		this.fullCalendar&&this.fullCalendar.setOption(option, value);
	}

	get_option(option) {
		return this.fullCalendar&&this.fullCalendar.getOption(option);
	}

	destroy() {
		this.fullCalendar&&this.fullCalendar.destroy();
	}

	getSelectAllow(selectInfo) {
		return momentjs().diff(selectInfo.start) <= 0
	}

	getValidRange() {
		return { start: momentjs().format("YYYY-MM-DD") }
	}

	set_loading_state(state) {
		state ? frappe.freeze(__("Please wait...")) : frappe.unfreeze();
	}

	calendar_options() {
		const me = this;

		let initialDate;
		const queryParamStartDate = new URLSearchParams(window.location.search).get("start_date");
		if (this.parent.date) {
			initialDate = momentjs(this.parent.date).format("YYYY-MM-DD");
		} else if (queryParamStartDate) {
			initialDate = queryParamStartDate;
		} else {
			initialDate = momentjs().add(1,'d').format("YYYY-MM-DD");
		}

		return {
			eventClassNames: function(arg) {
				return ['booking-calendar', arg.event.extendedProps.status || ""]
			},
			initialView: "dayGridMonth",
			contentHeight: 'auto',
			headerToolbar: me.get_header_toolbar(),
			weekends: true,
			buttonText: {
				today: __("Today"),
				timeGridWeek: __("Week"),
				listDay: __("Day")
			},
			plugins: [
				timeGridPlugin,
				listPlugin,
				interactionPlugin,
				dayGridPlugin
			],
			showNonCurrentDates: false,
			locale: this.locale,
			timeZone: frappe.boot.timeZone || 'UTC',
			initialDate: initialDate,
			noEventsContent: __("No slot available"),
			selectAllow: this.getSelectAllow,
			validRange: this.getValidRange,
			displayEventTime: false,
			dateClick: function(info) {
				me.booking_selector = new BookingSelector({
					parent: me,
					date_info: info
				})
			},
			datesSet: (info) => {
				this.booking_selector&&this.booking_selector.empty();
			},
			events: function(info, callback) {
				frappe.call("erpnext.venue.doctype.item_booking.item_booking.get_availabilities", {
					start: momentjs(info.start).format("YYYY-MM-DD"),
					end: momentjs(info.end).format("YYYY-MM-DD"),
					item: me.parent.item,
					uom: me.parent.uom
				}).then(result => {
					me.slots = result.message;
					callback(result.message);

					if (me.parent.date && !me.booking_selector) {
						me.booking_selector = new BookingSelector({
							parent: me,
							date_info: {date: me.parent.date}
						})
					} else {
						me.booking_selector && me.booking_selector.make()
					}
				})
			},
		}
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
				item: this.parent.parent.item,
				uom: this.parent.parent.uom
			}
		}).then(r => {
			if (r.message) {
				this.credits = r.message;
			}
			this.slots = this.parent.slots.filter(s => (
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
		const slots_div = this.slots.length ? this.slots.sort((a,b) => new Date(a.start) - new Date(b.start)).map(s => {
			const number_indicator = s.number > 0 ? `<div class="cart-indicator list-indicator ml-0">${s.number}</div>` : ""

			return `<div class="timeslot-options mb-4 px-4" data-slot-id="${s.id}">
				<button class="btn btn-outline-secondary ${s.status}" type="button">
					<div class="d-flex justify-content-center">
						<div class="mx-auto">
							${momentjs(s.start).locale(this.parent.locale).format('LT')} - ${momentjs(s.end).locale(this.parent.locale).format('LT')}
						</div>
						${number_indicator}
					</div>
				</button>
			</div>`
		}): [];

		this.$content = $(`<div>
			<h2 class="timeslot-options-title text-muted mb-4">${this.date_info.date ? momentjs(this.date_info.date).locale(this.parent.locale).format('LL') : ""}</h2>
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
			item: this.parent.parent.item,
			uom: this.parent.parent.uom,
			user: frappe.session.user,
			status: this.parent.skip_cart ? "Confirmed": null,
			with_credits: with_credits
		}).then(r => {
			console.log(r)
			if (!this.parent.skip_cart) {
				this.update_cart(r.message.name, 1)
			} else {
				this.parent.fullCalendar&&this.parent.fullCalendar.refetchEvents();
			}
		})
	}

	remove_booked_slot(booking_id) {
		if (!this.parent.skip_cart) {
			this.update_cart(booking_id, 0)
		} else {
			frappe.call("erpnext.venue.doctype.item_booking.item_booking.remove_booked_slot", {
				name: booking_id
			}).then(r => {
				this.parent.fullCalendar&&this.parent.fullCalendar.refetchEvents();
			})
		}
	}

	update_cart(booking, qty) {
		erpnext.e_commerce.shopping_cart.shopping_cart_update({
			item_code: this.parent.parent.item,
			qty: qty,
			uom: this.parent.parent.uom,
			booking: booking,
			cart_dropdown: true,
		}).then(() => {
			this.parent.fullCalendar&&this.parent.fullCalendar.refetchEvents();
		})
	}
}
