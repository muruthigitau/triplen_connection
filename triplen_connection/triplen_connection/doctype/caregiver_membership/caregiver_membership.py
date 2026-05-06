# Copyright (c) 2026, David Gitau and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime
from payments.utils import get_payment_gateway_controller


class CaregiverMembership(Document):
	def validate(self):
		self.validate_dates()

	def on_submit(self):
		self.create_membership_payment()

	def on_payment_authorized(self, payment_status: str):
		if payment_status in ("Authorized", "Completed"):
			payment = frappe.get_value(
				"Membership Payment", {"membership": self.name, "docstatus": ["<", 2]}, "name"
			)

			if payment:
				pay_doc = frappe.get_doc("Membership Payment", payment)
				pay_doc.paid = 1
				pay_doc.flags.ignore_permissions = True
				pay_doc.save()

				if pay_doc.docstatus == 0:
					pay_doc.submit()

			self.db_set("status", "Active")

	def validate_dates(self):
		if self.date_from and self.membership_duration:
			calculated_date_to = add_to_date(self.date_from, seconds=self.membership_duration)

			if get_datetime(self.date_to) != get_datetime(calculated_date_to):
				self.date_to = calculated_date_to

		if self.date_to and self.date_from and get_datetime(self.date_to) < get_datetime(self.date_from):
			frappe.throw("End date cannot be before start date.")

		if get_datetime(self.date_to) < now_datetime():
			self.status = "Expired"

	def create_membership_payment(self):
		payment = frappe.new_doc("Membership Payment")
		payment.membership = self.name
		payment.amount = self.amount
		payment.currency = self.currency
		payment.date = frappe.utils.today()

		if self.status == "Active":
			payment.paid = 1

		payment.flags.ignore_permissions = True
		payment.insert()
		payment.submit()


@frappe.whitelist()
def set_expired_memberships():
	now = now_datetime()

	expired_memberships = frappe.get_all(
		"Caregiver Membership",
		filters={"status": ["!=", "Expired"], "date_to": ["<", now], "docstatus": 1},
		pluck="name",
	)

	for name in expired_memberships:
		frappe.db.set_value("Caregiver Membership", name, "status", "Expired")

	if expired_memberships:
		frappe.db.commit()


# @frappe.whitelist()
# def get_payment_url(
# 	membership_name, gateway, redirect_to="https://triplencaregiversconnection.com/dashboard"
# ):
# 	membership = frappe.get_doc("Caregiver Membership", membership_name)

# 	controller = get_controller(gateway)

# 	payment_details = {
# 		"amount": membership.amount,
# 		"currency": membership.currency,
# 		"description": f"Membership Payment for {membership.user}",
# 		"title": f"Payment for Caregiver Membership: {membership.name}",
# 		"reference_doctype": "Caregiver Membership",
# 		"reference_docname": membership.name,
# 		"payer_name": membership.user,
# 		"payer_email": membership.user,
# 		"payment_gateway": gateway,
# 		"order_id": membership.name,
# 		"redirect_to": redirect_to,
# 	}

# 	if hasattr(controller, "create_order"):
# 		order = controller.create_order(**payment_details)
# 		payment_details.update({"order_id": order.get("id")})

# 	expected_keys = (
# 		"amount",
# 		"title",
# 		"description",
# 		"reference_doctype",
# 		"reference_docname",
# 		"payer_name",
# 		"payer_email",
# 		"currency",
# 		"payment_gateway",
# 		"redirect_to",
# 	)

# 	filtered_details = {k: v for k, v in payment_details.items() if k in expected_keys}

# 	if "order_id" in payment_details:
# 		filtered_details["order_id"] = payment_details["order_id"]

# 	url = controller.get_payment_url(**filtered_details)

# 	return url


@frappe.whitelist()
def get_payment_url(
	membership_name, gateway, redirect_to="https://triplencaregiversconnection.com/dashboard"
):
	membership = frappe.get_doc("Caregiver Membership", membership_name)

	stripe_settings = frappe.db.get_value("Payment Gateway", gateway, "gateway_controller")

	if not stripe_settings:
		frappe.throw(_("Stripe Settings not found for gateway: {0}").format(gateway))

	stripe_request = frappe.get_doc(
		{
			"doctype": "Stripe Request",
			"stripe_settings": stripe_settings,
			"amount": membership.amount,
			"currency": membership.currency,
			"reference_doctype": "Caregiver Membership",
			"reference_docname": membership.name,
			"title": _("Payment for Membership: {0}").format(membership.name),
			"description": _("Membership Payment for {0}").format(membership.user),
			"payer_name": frappe.db.get_value("User", membership.user, "full_name") or membership.user,
			"payer_email": membership.user,
			"redirect_url": redirect_to,
			"paid": 0,
		}
	)
	stripe_request.flags.ignore_permissions = True
	stripe_request.insert(ignore_permissions=True)
	stripe_request.submit()
	base_url = "/stripe"
	payment_url = f"{base_url}?request_id={stripe_request.name}"

	return payment_url


def get_controller(payment_gateway):

	return get_payment_gateway_controller(payment_gateway)
