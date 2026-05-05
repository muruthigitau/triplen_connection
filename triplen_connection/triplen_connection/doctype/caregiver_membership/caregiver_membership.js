// Copyright (c) 2026, David Gitau and contributors
// For license information, please see license.txt

frappe.ui.form.on("Caregiver Membership", {
	refresh(frm) {
		if (frm.doc.status === "Pending" && frm.doc.membership_type) {
			frm.add_custom_button(__("Pay Now"), () => {
				show_payment_options(frm);
			}).addClass("btn-primary");
		}
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.date_from) {
			frm.set_value("date_from", frappe.datetime.now_datetime());
		}
	},

	date_from(frm) {
		calculate_date_to(frm);
	},

	membership_duration(frm) {
		calculate_date_to(frm);
	},
});

function calculate_date_to(frm) {
	if (frm.doc.date_from && frm.doc.membership_duration) {
		let date_to = frappe.datetime.add_seconds(frm.doc.date_from, frm.doc.membership_duration);
		frm.set_value("date_to", date_to);
	}
}

function show_payment_options(frm) {
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Caregiver Membership Type",
			name: frm.doc.membership_type,
		},
		callback: function (r) {
			if (r.message && r.message.payment_methods && r.message.payment_methods.length > 0) {
				const methods = r.message.payment_methods;

				if (methods.length === 1) {
					initiate_payment(frm, methods[0]);
				} else {
					let d = new frappe.ui.Dialog({
						title: __("Select Payment Method"),
						fields: [
							{
								label: __("Payment Gateway"),
								fieldname: "gateway",
								fieldtype: "Select",
								options: methods.map((m) => m.payment_gateway),
								reqd: 1,
							},
						],
						primary_action_label: __("Proceed to Pay"),
						primary_action(values) {
							const selected_method = methods.find(
								(m) => m.payment_gateway === values.gateway,
							);
							initiate_payment(frm, selected_method);
							d.hide();
						},
					});
					d.show();
				}
			} else {
				frappe.msgprint(__("No payment methods configured for this membership type."));
			}
		},
	});
}

function initiate_payment(frm, method) {
	frappe.call({
		method: "triplen_connection.triplen_connection.doctype.caregiver_membership.caregiver_membership.get_payment_url",
		args: {
			membership_name: frm.doc.name,
			gateway: method.payment_gateway,
			gateway_controller: method.gateway_controller,
			gateway_settings: method.gateway_settings,
		},
		callback: function (r) {
			if (r.message) {
				const url = typeof r.message === "string" ? r.message : r.message.url;
				console.log(url);

				if (url) {
					window.open(url, "_blank");
				}
			}
		},
	});
}
