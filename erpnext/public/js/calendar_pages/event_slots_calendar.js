// Copyright (c) 2020, Dokos SAS and Contributors
// See license.txt

import "./base_calendar";

erpnext.eventSlotsBookings = class EventSlotsBookings {
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
		this.calendar = new EventSlotsCalendar({
			wrapper: this.wrapper,
			parent: this,
		})
	}
}

class EventSlotsCalendar extends frappe.ui.BaseWebCalendar {
	init(opts) {
		this.parent = opts.parent;
		this.render();
	}

	calendar_options() {
		return Object.assign(super.calendar_options(), {
			eventClassNames: "event-slot-calendar",
			initialView: frappe.is_mobile() ? "listDay" : "timeGridWeek",
			headerToolbar: {
				left: frappe.is_mobile() ? "listWeek,listDay" : "dayGridMonth,timeGridWeek,listDay",
				center: frappe.is_mobile() ? "" : "prev,title,next",
				right: frappe.is_mobile() ? "prev,title,next" : "today",
			},
			eventContent(info) {
				return { html: `${info.event.extendedProps.description}`};
			},
		});
	}

	onEventsUpdated() {
		this.set_min_max_times({ min: "09:00:00", max: "17:00:00"});
	}

	getEvents(parameters) {
		return this.getAvailableSlots(parameters);
	}

	getAvailableSlots(parameters) {
		return frappe.call("erpnext.venue.doctype.event_slot.event_slot.get_available_slots", {
			start: moment(parameters.start).format("YYYY-MM-DD"),
			end: moment(parameters.end).format("YYYY-MM-DD")
		}).then(result => {
			return result.message || []
		});
	}

	onEventClick(event) {
		const me = this;
		const dialog = new frappe.ui.Dialog({
			size: "large",
			title: __(event.event.title),
			fields: [
				{
					"fieldtype": "HTML",
					"fieldname": "event_description"
				}
			],
			primary_action_label: __("Register"),
			primary_action() {
				frappe.confirm(__("Do you want to register yourself for this slot ?"), () => {
					frappe.call("erpnext.venue.doctype.event_slot_booking.event_slot_booking.register_for_slot", {
						slot: event.event.id
					})
					.then(() => {
						dialog.hide()
						me.refetchEvents();
					})
				});
			}
		});
		const description = event.event.extendedProps.content ? event.event.extendedProps.content : `<div>${__("No description")}</div>`
		dialog.fields_dict.event_description.$wrapper.html(description);
		$(dialog.footer).prepend(`
			<span class="mr-2">
				${event.event.extendedProps.booked_by_user ? __("You are already registered") + "<br/>" : ""}
				${(event.event.extendedProps.available_slots - event.event.extendedProps.booked_slots) + " " + __("slots available")}
			</span>`
		)

		if (event.event.extendedProps.booked_slots >= event.event.extendedProps.available_slots || event.event.extendedProps.booked_by_user) {
			dialog.disable_primary_action();
		}
		dialog.show()
	}

	getSelectAllow(selectInfo) {
		console.log(selectInfo.start, new Date());
		return moment().diff(selectInfo.start) <= 0
	}

	getValidRange() {
		return { start: moment().format("YYYY-MM-DD") }
	}
}
