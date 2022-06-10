// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// shopping cart
frappe.provide("erpnext.e_commerce.shopping_cart");
var shopping_cart = erpnext.e_commerce.shopping_cart;

var getParams = function (url) {
	var params = [];
	var parser = document.createElement('a');
	parser.href = url;
	var query = parser.search.substring(1);
	var vars = query.split('&');
	for (var i = 0; i < vars.length; i++) {
		var pair = vars[i].split('=');
		params[pair[0]] = decodeURIComponent(pair[1]);
	}
	return params;
};

frappe.ready(function () {
	var full_name = frappe.session && frappe.session.user_fullname;
	// update user
	if (full_name) {
		$('.navbar li[data-label="User"] a')
			.html('<i class="fa fa-fixed-width fa fa-user"></i> ' + full_name);
	}
	// set coupon code and sales partner code

	var url_args = getParams(window.location.href);

	var referral_coupon_code = url_args['cc'];
	var referral_sales_partner = url_args['sp'];

	var d = new Date();
	// expires within 30 minutes
	d.setTime(d.getTime() + (0.02 * 24 * 60 * 60 * 1000));
	var expires = "expires=" + d.toUTCString();
	if (referral_coupon_code) {
		document.cookie = "referral_coupon_code=" + referral_coupon_code + ";" + expires + ";path=/";
	}
	if (referral_sales_partner) {
		document.cookie = "referral_sales_partner=" + referral_sales_partner + ";" + expires + ";path=/";
	}
	referral_coupon_code = frappe.get_cookie("referral_coupon_code");
	referral_sales_partner = frappe.get_cookie("referral_sales_partner");

	if (referral_coupon_code && $(".tot_quotation_discount").val() == undefined) {
		$(".txtcoupon").val(referral_coupon_code);
	}
	if (referral_sales_partner) {
		$(".txtreferral_sales_partner").val(referral_sales_partner);
	}

	// update login
	shopping_cart.show_shoppingcart_dropdown();
	shopping_cart.set_cart_count();
	shopping_cart.show_cart_navbar();
});

$.extend(shopping_cart, {
	show_shoppingcart_dropdown: function () {
		$(".shopping-cart").on('shown.bs.dropdown', function () {
			if (!$('.shopping-cart-menu .cart-container').length) {
				return frappe.call({
					method: 'erpnext.e_commerce.shopping_cart.cart.get_shopping_cart_menu',
					callback: function(r) {
						if (r.message) {
							$('.shopping-cart-menu').html(r.message);
						}
					}
				});
			}
		});
	},

	update_cart: function (opts) {
		if (frappe.session.user === "Guest") {
			if (localStorage) {
				localStorage.setItem("last_visited", window.location.pathname);
			}
			frappe.call('erpnext.e_commerce.api.get_guest_redirect_on_action').then((res) => {
				window.location.href = res.message || "/login";
			});
		} else {
			shopping_cart.freeze();
			return frappe.call({
				type: "POST",
				method: "erpnext.e_commerce.shopping_cart.cart.update_cart",
				args: {
					item_code: opts.item_code,
					qty: opts.qty,
					booking: opts.booking,
					additional_notes: opts.additional_notes !== undefined ? opts.additional_notes : undefined,
					with_items: opts.with_items || 0
				},
				btn: opts.btn,
				callback: function(r) {
					shopping_cart.unfreeze();
					shopping_cart.set_cart_count(true);
					if(opts.callback)
						opts.callback(r);
				}
			});
		}
	},

	set_cart_count: function(animate=false) {
		$(".intermediate-empty-cart").remove();

		var cart_count = frappe.get_cookie("cart_count");
		if (frappe.session.user === "Guest") {
			cart_count = 0;
		}

		if (cart_count) {
			$(".shopping-cart").toggleClass('hidden', false);
		}

		var $cart = $('.cart-icon');
		var $badge = $cart.find("#cart-count");

		if (parseInt(cart_count) === 0 || cart_count === undefined) {
			$cart.css("display", "none");
			$(".cart-tax-items").hide();
			$(".btn-place-order").hide();
			$(".cart-payment-addresses").hide();

			let intermediate_empty_cart_msg = `
				<div class="text-center w-100 intermediate-empty-cart mt-4 mb-4 text-muted">
					${ __("Cart is Empty") }
				</div>
			`;
			$(".cart-table").after(intermediate_empty_cart_msg);
		}
		else {
			$cart.css("display", "inline");
			$("#cart-count").text(cart_count);
		}

		if (cart_count) {
			$badge.html(cart_count);

			if (animate) {
				$cart.addClass("cart-animate");
				setTimeout(() => {
					$cart.removeClass("cart-animate");
				}, 500);
			}
		} else {
			$badge.remove();
		}
	},

	shopping_cart_update: function ({ item_code, qty, cart_dropdown, additional_notes, uom, booking }) {
		frappe.freeze();
		return shopping_cart.update_cart({
			item_code,
			qty,
			additional_notes,
			with_items: 1,
			btn: this,
			uom: uom,
			booking: booking,
			callback: function(r) {
				if(!r.exc) {
					$(".cart-items").html(r.message.items);
					$(".cart-tax-items").html(r.message.total);
					$(".payment-summary").html(r.message.taxes_and_totals);
					shopping_cart.set_cart_count();

					if (cart_dropdown != true) {
						$(".cart-icon").hide();
					}
				}
			},
		});
	},

	show_cart_navbar: function () {
		frappe.call({
			method: "erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings.is_cart_enabled",
			callback: function(r) {
				$(".shopping-cart").toggleClass('hidden', r.message ? false : true);
			}
		});
	},

	new_cart_address: function (reload) {
		return new Promise(resolve => {
			const d = new frappe.ui.Dialog({
				title: __('New Address'),
				fields: [
					{
						label: __('Address Title'),
						fieldname: 'address_title',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('Address Line 1'),
						fieldname: 'address_line1',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('Address Line 2'),
						fieldname: 'address_line2',
						fieldtype: 'Data'
					},
					{
						label: __('City/Town'),
						fieldname: 'city',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('State'),
						fieldname: 'state',
						fieldtype: 'Data'
					},
					{
						label: __('Country'),
						fieldname: 'country',
						fieldtype: 'Link',
						options: 'Country',
						reqd: 1,
						only_select: 1
					},
					{
						fieldname: "column_break0",
						fieldtype: "Column Break",
						width: "50%"
					},
					{
						label: __('Address Type'),
						fieldname: 'address_type',
						fieldtype: 'Select',
						options: [
							'Billing',
							'Shipping'
						],
						default: 'Shipping',
						reqd: 1
					},
					{
						label: __('Postal Code'),
						fieldname: 'pincode',
						fieldtype: 'Data'
					},
					{
						fieldname: "phone",
						fieldtype: "Data",
						label: "Phone"
					},
				],
				primary_action_label: __('Save'),
				primary_action: (values) => {
					frappe.call('erpnext.e_commerce.shopping_cart.cart.add_new_address', { doc: values })
						.then(r => {
							frappe.call({
								method: "erpnext.e_commerce.shopping_cart.cart.update_cart_address",
								args: {
									address_type: r.message.address_type,
									address_name: r.message.name
								},
								callback: function (r) {
									resolve();
									d.hide();

									reload && window.location.reload();
								}
							});
						});

				}
			})
			d.$wrapper.find(".modal-content").addClass("frappe-card");
			d.show();
		});
	},

	bind_add_to_cart_action() {
		$('.page_content').on('click', '.btn-add-to-cart-list', (e) => {
			const $btn = $(e.currentTarget);
			$btn.prop('disabled', true);

			if (frappe.session.user==="Guest") {
				if (localStorage) {
					localStorage.setItem("last_visited", window.location.pathname);
				}
				frappe.call('erpnext.e_commerce.api.get_guest_redirect_on_action').then((res) => {
					window.location.href = res.message || "/login";
				});
				return;
			}

			$btn.addClass('hidden');
			$btn.closest('.cart-action-container').addClass('d-flex');
			$btn.parent().find('.go-to-cart').removeClass('hidden');
			$btn.parent().find('.go-to-cart-grid').removeClass('hidden');
			$btn.parent().find('.cart-indicator').removeClass('hidden');

			const item_code = $btn.data('item-code');
			erpnext.e_commerce.shopping_cart.update_cart({
				item_code,
				qty: 1,
				cart_dropdown: true
			});

		});
	},

	freeze() {
		if (window.location.pathname !== "/cart") return;

		if (!$('#freeze').length) {
			let freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.appendTo("body");

			setTimeout(function() {
				freeze.addClass("show");
			}, 1);
		} else {
			$("#freeze").addClass("show");
		}
	},

	unfreeze() {
		if ($('#freeze').length) {
			let freeze = $('#freeze').removeClass("show");
			setTimeout(function() {
				freeze.remove();
			}, 1);
		}
	}
});
