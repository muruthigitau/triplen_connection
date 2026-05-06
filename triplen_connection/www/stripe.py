import json

import frappe
from frappe import _
from frappe.utils import fmt_money
from payments.payment_gateways.doctype.stripe_settings.stripe_settings import (
	get_gateway_controller,
)

no_cache = 1


def get_context(context):
	context.no_cache = 1
	request_id = frappe.form_dict.get("request_id")

	if not request_id:
		frappe.redirect_to_message(_("Invalid Request"), _("No request ID provided."))
		return

	try:
		doc = frappe.get_doc("Stripe Request", request_id)

		context.stripe_request_id = request_id
		context.paid = doc.paid
		context.redirect_url = doc.redirect_url or "/"
		context.reference_doctype = doc.reference_doctype
		context.reference_docname = doc.reference_docname
		context.payment_gateway = doc.payment_gateway
		context.payer_name = doc.payer_name
		context.payer_email = doc.payer_email
		context.description = doc.description
		context.title = doc.title
		context.currency = doc.currency
		context.amount = fmt_money(amount=doc.amount, currency=doc.currency)

		gateway_controller = doc.payment_gateway

		context.publishable_key = frappe.db.get_value(
			"Stripe Settings", gateway_controller, "publishable_key"
		)
		context.image = frappe.db.get_value("Stripe Settings", gateway_controller, "header_img")

		if doc.paid:
			context.title = _("Payment Successful")
			context.description = _("This payment has already been completed.")

	except frappe.DoesNotExistError:
		frappe.redirect_to_message(_("Not Found"), _("The requested payment record does not exist."))


@frappe.whitelist(allow_guest=True)
def make_payment(
	stripe_token_id,
	data,
	reference_doctype=None,
	reference_docname=None,
	payment_gateway=None,
	stripe_request_id=None,
):
	stripe_request = frappe.get_doc("Stripe Request", stripe_request_id)

	if stripe_request.paid:
		return {"status": "Completed", "redirect_to": stripe_request.redirect_url or "/"}

	payload = json.loads(data)

	success_url = stripe_request.redirect_url or "/"

	payload.update(
		{
			"stripe_token_id": stripe_token_id,
			"amount": stripe_request.amount,
			"currency": stripe_request.currency,
			"description": stripe_request.description,
			"payer_email": stripe_request.payer_email,
			"payer_name": stripe_request.payer_name,
			"redirect_url": success_url,
			"redirect_to": success_url,
		}
	)

	gateway_controller = stripe_request.payment_gateway
	doc = frappe.get_doc("Stripe Settings", gateway_controller)

	doc.flags.ignore_permissions = True
	payment_response = doc.create_request(payload)

	if payment_response.get("status") == "Completed":
		stripe_request.paid = 1
		stripe_request.flags.ignore_permissions = True
		ref_doc = frappe.get_doc(stripe_request.reference_doctype, stripe_request.reference_docname)
		try:
			ref_doc.on_payment_authorized(payment_response.get("status"))
		except AttributeError:
			frappe.log_error(
				"Stripe Payment: Missing on_payment_authorized method",
				f"{stripe_request.reference_doctype} does not have an on_payment_authorized method.",
			)
		stripe_request.save()
		frappe.db.commit()
		payment_response["redirect_to"] = success_url

	return payment_response
