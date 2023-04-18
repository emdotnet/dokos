// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// JS exclusive to /checkout page
frappe.provide("erpnext.e_commerce.shopping_cart");
var shopping_cart = erpnext.e_commerce.shopping_cart;

$.extend(shopping_cart, {
	bind_events: function() {
		shopping_cart.bind_address_picker_dialog();
		shopping_cart.bind_place_order();
		shopping_cart.bind_request_quotation();
		shopping_cart.bind_coupon_code();
		shopping_cart.bind_shipping_method();
	},

	bind_address_picker_dialog: function() {
		const d = this.get_update_address_dialog();
		$(".cart-container").on("click", '.btn-change-address', (e) => {
			const type = $(e.currentTarget).parents('.address-container').attr('data-address-type');
			$(d.get_field('address_picker').wrapper).html(
				this.get_address_template(type)
			);
			d.show();
		});
	},

	bind_shipping_method() {
		$(".cart-container").on("change", ".shipping-methods-list input[name=shipping]", (e) => {
			const shipping_method = e.target.value;
			shopping_cart.apply_shipping_rule(shipping_method);
		});
	},

	get_update_address_dialog() {
		let d = new frappe.ui.Dialog({
			title: __("Select Address"),
			fields: [{
				'fieldtype': 'HTML',
				'fieldname': 'address_picker',
			}],
			primary_action_label: __('Set Address'),
			primary_action: () => {
				const $card = d.$wrapper.find('.address-card.active');
				const address_type = $card.closest('[data-address-type]').attr('data-address-type');
				const address_name = $card.closest('[data-address-name]').attr('data-address-name');
				frappe.call({
					type: "POST",
					method: "erpnext.e_commerce.shopping_cart.cart.update_cart_address",
					freeze: true,
					args: {
						address_type,
						address_name
					},
					callback: function(r) {
						d.hide();
						if (!r.exc) {
							shopping_cart.clear_error();
							shopping_cart.render_form_server_side(r.message);
						}
					}
				});
			}
		});
		d.disable_primary_action();
		return d;
	},

	get_address_template(type) {
		return {
			shipping: `<div class="mb-3" data-section="shipping-address">
				<div class="row no-gutters" data-fieldname="shipping_address_name">
					{% for address in shipping_addresses %}
						<div class="mr-3 mb-3 w-100" data-address-name="{{address.name}}" data-address-type="shipping"
							{% if doc.shipping_address_name == address.name %} data-active {% endif %}>
							{% include "templates/includes/cart/address_picker_card.html" %}
						</div>
					{% endfor %}
				</div>
			</div>`,
			billing: `<div class="mb-3" data-section="billing-address">
				<div class="row no-gutters" data-fieldname="customer_address">
					{% for address in billing_addresses %}
						<div class="mr-3 mb-3 w-100" data-address-name="{{address.name}}" data-address-type="billing"
							{% if doc.shipping_address_name == address.name %} data-active {% endif %}>
							{% include "templates/includes/cart/address_picker_card.html" %}
						</div>
					{% endfor %}
				</div>
			</div>`,
		}[type];
	},

	apply_shipping_rule(rule, btn) {
		frappe.freeze(__("Updating", [], "Freeze message while updating a document"));
		return frappe.call({
			btn: btn,
			type: "POST",
			method: "erpnext.e_commerce.shopping_cart.cart.apply_shipping_rule",
			args: { shipping_rule: rule },
			callback(r) {
				frappe.unfreeze();
				if (!r.exc) {
					shopping_cart.clear_error();
					shopping_cart.render_form_server_side(r.message);
				}
			}
		});
	},

	bind_coupon_code: function() {
		$(".cart-container").on("click", ".bt-coupon", function() {
			shopping_cart.apply_coupon_code(this);
		});
	},

	apply_coupon_code: function(btn) {
		return frappe.call({
			type: "POST",
			method: "erpnext.e_commerce.shopping_cart.cart.apply_coupon_code",
			btn: btn,
			args : {
				applied_code : $('.txtcoupon').val(),
				applied_referral_sales_partner: $('.txtreferral_sales_partner').val()
			},
			callback: function(r) {
				if (r && r.message){
					location.reload();
				}
			}
		});
	}
});

frappe.ready(function() {
	if (window.location.pathname === "/checkout") {
		$(".cart-icon").hide();
	}
	shopping_cart.parent = $(".cart-container");
	shopping_cart.bind_events();
});
