import json

import frappe
from frappe import _
from frappe.utils import cint, fmt_money
from payments.payment_gateways.doctype.stripe_settings.stripe_settings import (
	get_gateway_controller,
)

no_cache = 1


def get_context(context):
	context.no_cache = 1
	request_id = frappe.form_dict.get("request_id")

	if not request_id:
		frappe.redirect_to_message(
			_("Invalid Request"), _("No request ID was provided. Please use a valid payment link.")
		)
		return

	try:
		stripe_request = frappe.get_doc("Stripe Request", request_id)

		context.stripe_request_id = request_id
		context.paid = stripe_request.paid
		context.redirect_url = stripe_request.redirect_url or "/"
		context.reference_doctype = stripe_request.reference_doctype
		context.reference_docname = stripe_request.reference_docname
		context.payment_gateway = stripe_request.payment_gateway
		context.payer_name = stripe_request.payer_name
		context.payer_email = stripe_request.payer_email
		context.description = stripe_request.description
		context.title = stripe_request.title
		context.currency = stripe_request.currency
		context.amount = fmt_money(amount=stripe_request.amount, currency=stripe_request.currency)

		if stripe_request.paid:
			context.title = _("Payment Successful")
			context.description = _("This payment has already been completed.")
			return

		gateway_controller = get_gateway_controller(
			context.reference_doctype, context.reference_docname, context.payment_gateway
		)

		context.publishable_key = get_api_key(gateway_controller)
		context.image = get_header_image(gateway_controller)

	except frappe.DoesNotExistError:
		frappe.redirect_to_message(_("Not Found"), _("The requested payment record does not exist."))


def get_api_key(gateway_controller):
	return frappe.db.get_value("Stripe Settings", gateway_controller, "publishable_key")


def get_header_image(gateway_controller):
	return frappe.db.get_value("Stripe Settings", gateway_controller, "header_img")


@frappe.whitelist(allow_guest=True)
def make_payment(stripe_token_id, stripe_request_id):
	stripe_request = frappe.get_doc("Stripe Request", stripe_request_id)

	if stripe_request.paid:
		return {"status": "Completed", "redirect_to": stripe_request.redirect_url or "/"}

	gateway_controller = get_gateway_controller(
		stripe_request.reference_doctype, stripe_request.reference_docname, stripe_request.payment_gateway
	)

	data = {
		"stripe_token_id": stripe_token_id,
		"amount": stripe_request.amount,
		"currency": stripe_request.currency,
		"description": stripe_request.description,
		"payer_email": stripe_request.payer_email,
	}

	payment_response = frappe.get_doc("Stripe Settings", gateway_controller).create_request(data)

	if payment_response.get("status") == "Completed":
		stripe_request.db_set("paid", 1)
		frappe.db.commit()
		payment_response["redirect_to"] = stripe_request.redirect_url or "/"

	return payment_response
