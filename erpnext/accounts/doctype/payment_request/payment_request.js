frappe.ui.form.on("Payment Request", {
	setup(frm) {
		frm.add_fetch("payment_gateway_account", "payment_account", "payment_account")
		frm.add_fetch("payment_gateway_account", "payment_gateway", "payment_gateway")
		frm.add_fetch("payment_gateways_template", "email_template", "email_template")
	},
	onload(frm) {
		if (frm.doc.reference_doctype) {
			frappe.call({
				method:"erpnext.accounts.doctype.payment_request.payment_request.get_print_format_list",
				args: {"ref_doctype": frm.doc.reference_doctype},
				callback:function(r){
					set_field_options("print_format", r.message["print_format"])
				}
			})
		}
	},
	refresh(frm) {
		if (!frm.is_new() && frm.doc.payment_key) {
			frm.web_link && frm.web_link.remove();
			frm.add_web_link(`/payments?link=${frm.doc.payment_key}`, __("See payment link"));
		}

		if(frm.doc.status !== "Paid" && !frm.is_new() && frm.doc.docstatus==1){
			frm.add_custom_button(__('Resend Payment Email'), function(){
				frappe.call({
					method: "erpnext.accounts.doctype.payment_request.payment_request.resend_payment_email",
					args: {"docname": frm.doc.name},
					freeze: true,
					freeze_message: __("Sending"),
					callback: function(r){
						if(!r.exc) {
							frappe.msgprint(__("Message Sent"));
						}
					}
				});
			}, __("Actions"));
		}

		if(frm.doc.status == "Initiated") {
			if (!frm.doc.payment_gateway_account) {
				frm.add_custom_button(__('Create Payment Entry'), function(){
					frappe.call({
						method: "erpnext.accounts.doctype.payment_request.payment_request.make_payment_entry",
						args: {"docname": frm.doc.name},
						freeze: true,
						callback: function(r){
							if(!r.exc) {
								var doc = frappe.model.sync(r.message);
								frappe.set_route("Form", r.message.doctype, r.message.name);
							}
						}
					});
				}).addClass("btn-primary");
			}

			if (!frm.doc.payment_gateway || frm.doc.payment_gateway_account.toLowerCase().includes("gocardless")) {
				frappe.call({
					method: "check_if_immediate_payment_is_autorized",
					doc: frm.doc,
				}).then(r => {
					if (r.message && r.message.length) {
						frm.trigger("process_payment_immediately");
					}
				})
			}
		}
	},
	process_payment_immediately(frm) {
		frm.add_custom_button(__('Process payment immediately'), function(){
			frappe.call({
				method: "process_payment_immediately",
				doc: frm.doc,
			}).then(r => {
					frm.reload_doc()
					frappe.show_alert({message:__("Payment successfully initialized"), indicator:'green'});
			})
		}, __("Actions"))
	},
	reference_name(frm) {
		if (frm.doc.reference_name) {
			frappe.call({
				method: "get_subscription_payment_gateways",
				doc: frm.doc,
			}).then(r => {
				if (r.message && r.message.length) {
					frm.doc.payment_gateways = []
					r.message.forEach(value => {
						const c = frm.add_child("payment_gateways");
						c.payment_gateway = value;
					})
					frm.refresh_fields("payment_gateways")
				}
			})
		}
	},
	email_template(frm) {
		if (frm.doc.email_template) {
			frappe.db.get_value("Email Template", frm.doc.email_template, ["subject", "response"], r => {
				if (r) {
					let signature = frappe.boot.user.email_signature || "";

					if(!frappe.utils.is_html(signature)) {
						signature = signature.replace(/\n/g, "<br>");
					}

					if(r.response && signature && r.response.includes(signature)) {
						signature = "";
					}
			
					const content = (r.response || "") + (signature ? ("<br>" + signature) : "");

					frm.set_value("subject", r.subject);
					frm.set_value("message", content);
				}
			})
		}
	},
	payment_gateways_template(frm) {
		if(frm.doc.payment_gateways_template) {
			frappe.model.with_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template, function() {
				const template = frappe.get_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template)
				frm.set_value('payment_gateways', template.payment_gateways.slice());
			});
		}
	}

})
