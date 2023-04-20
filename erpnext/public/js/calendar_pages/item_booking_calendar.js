// Copyright (c) 2020, Dokos SAS and Contributors
// See license.txt

import './base_calendar';

erpnext.itemBookingCalendar = class ItemBookingCalendar {
	constructor(opts) {
		Object.assign(this, opts);
		this.calendar = {};
		this.wrapper = document.getElementById(this.parentId);
		this.show()
	}

	show() {
		this.build_calendar()
	}

	build_calendar() {
		this.calendar = new ItemCalendar({
			wrapper: this.wrapper,
			parent: this,
		})
	}
}

class ItemCalendar extends frappe.ui.BaseWebCalendar {
	init(opts) {
		this.parent = opts.parent;
	}

	get_header_toolbar() {
		return {
			left: frappe.is_mobile() ? 'today' : 'dayGridMonth,timeGridWeek,listDay',
			center: 'prev,title,next',
			right: frappe.is_mobile() ? '' : 'today',
		}
	}

	calendar_options() {
		return Object.assign(super.calendar_options(), {
			eventClassNames: "item-booking-calendar",
			initialView: frappe.is_mobile() ? "listDay" : "timeGridWeek",
			noEventsContent: __("No events to display"),
			slotMinTime: "08:00:00",
			slotMaxTime: "20:00:00",
			allDayContent: __("All Day"),
			displayEventTime: console.log,
		})
	}

	onEventsUpdated() {
		this.set_min_max_times({ min: "09:00:00", max: "17:00:00" });
	}

	getEvents(parameters) {
		return this.getBookings(parameters);
	}

	getBookings(parameters) {
		return frappe.call("erpnext.venue.doctype.item_booking.item_booking.get_bookings_list_for_map", {
			start: this.format_ymd(parameters.start),
			end: this.format_ymd(parameters.end),
		}).then(result => {
			return result.message || [];
		})
	}

	onEventClick(event) {
		const props = event.event.extendedProps;
		if (props?.status === "In cart") {
			window.location.href = "/cart";
			return;
		}

		if (
			this.parent.can_cancel == "0" ||
			frappe.datetime.get_diff(event.event.start, frappe.datetime.add_minutes(frappe.datetime.nowdate(), parseInt(this.parent.cancellation_delay))) <= 0
		) {
			return
		}

		frappe.confirm(__('Do you want to cancel this booking ?'), () => {
			frappe.call({
				method: "erpnext.venue.doctype.item_booking.item_booking.cancel_appointment",
				args: {
					id: event.event.id
				}
			}).then(() => {
				this.refetchEvents();
			})
		});
	}
}
