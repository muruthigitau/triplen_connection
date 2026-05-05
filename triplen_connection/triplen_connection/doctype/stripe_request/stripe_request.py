# Copyright (c) 2026, David Gitau and contributors
# For license information, please see license.txt

import json
from urllib.parse import urlencode

import frappe
import stripe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, fmt_money, get_url, now


class StripeRequest(Document):
	def validate(self):
		"""Validate document before save"""
		if self.is_new():
			self.status = "Draft"
			self.request_date = now()
			self.created_at = now()

		self.validate_amount()
		self.validate_expiry()
		self.set_amount_in_cents()
		self.validate_stripe_settings()

		# Auto-fetch missing data from reference document
		self.auto_fetch_from_reference()

	def auto_fetch_from_reference(self):
		"""Auto-fetch payer details, amount, currency from reference document if not provided"""
		if not self.reference_doctype or not self.reference_docname:
			return

		# Only fetch if fields are empty
		if self.payer_name and self.payer_email and self.amount:
			return

		try:
			doc = frappe.get_doc(self.reference_doctype, self.reference_docname)

			# Auto-fetch amount
			if not self.amount:
				self.amount = self.get_amount_from_document(doc)
				if not self.amount:
					frappe.throw(
						_("Could not auto-fetch amount from {0} {1}. Please enter manually.").format(
							self.reference_doctype, self.reference_docname
						)
					)

			# Auto-fetch currency
			if not self.currency:
				self.currency = self.get_currency_from_document(doc) or "USD"

			# Auto-fetch payer name
			if not self.payer_name:
				self.payer_name = self.get_name_from_document(doc) or "Customer"

			# Auto-fetch payer email
			if not self.payer_email:
				self.payer_email = self.get_email_from_document(doc)

			# Auto-generate title if not provided
			if not self.title or self.title == "Payment Request":
				self.title = f"Payment for {self.reference_doctype} {self.reference_docname}"

			# Auto-generate description if not provided
			if not self.description:
				self.description = self.get_description_from_document(doc)

		except Exception:
			frappe.log_error(frappe.get_traceback(), "Auto-fetch from reference error")

	def get_amount_from_document(self, doc):
		"""Extract amount from various doctypes"""
		amount_fields = [
			"grand_total",
			"total",
			"amount",
			"net_total",
			"outstanding_amount",
			"balance",
			"due_amount",
		]

		for field in amount_fields:
			if hasattr(doc, field):
				value = flt(getattr(doc, field, 0))
				if value > 0:
					return value

		# Try to get from items table
		if hasattr(doc, "items") and doc.items:
			total = 0
			for item in doc.items[:5]:
				if hasattr(item, "amount"):
					total += flt(item.amount)
				elif hasattr(item, "net_amount"):
					total += flt(item.net_amount)
			if total > 0:
				return total

		return 0

	def get_currency_from_document(self, doc):
		"""Extract currency from document"""
		currency_fields = ["currency", "company_currency", "transaction_currency"]

		for field in currency_fields:
			if hasattr(doc, field):
				currency = getattr(doc, field)
				if currency:
					return currency

		return None

	def get_email_from_document(self, doc):
		"""Extract email from document"""
		email_fields = ["email", "customer_email", "contact_email", "buyer_email", "payer_email"]

		for field in email_fields:
			if hasattr(doc, field):
				email = getattr(doc, field)
				if email:
					return email

		# Try to get from customer/supplier
		if hasattr(doc, "customer") and doc.customer:
			customer = frappe.get_doc("Customer", doc.customer)
			if customer.email_id:
				return customer.email_id

		if hasattr(doc, "supplier") and doc.supplier:
			supplier = frappe.get_doc("Supplier", doc.supplier)
			if supplier.email_id:
				return supplier.email_id

		return None

	def get_name_from_document(self, doc):
		"""Extract customer/supplier name from document"""
		name_fields = ["customer_name", "supplier_name", "contact_name", "buyer_name", "payer_name"]

		for field in name_fields:
			if hasattr(doc, field):
				name = getattr(doc, field)
				if name:
					return name

		# Try to get from customer/supplier
		if hasattr(doc, "customer") and doc.customer:
			customer = frappe.get_doc("Customer", doc.customer)
			return customer.customer_name

		if hasattr(doc, "supplier") and doc.supplier:
			supplier = frappe.get_doc("Supplier", doc.supplier)
			return supplier.supplier_name

		return None

	def get_description_from_document(self, doc):
		"""Generate description based on document type"""
		description = f"Payment for {self.reference_doctype} {self.reference_docname}"

		# Add specific details based on doctype
		if self.reference_doctype == "Sales Invoice":
			if hasattr(doc, "customer_name"):
				description = f"Invoice payment for {doc.customer_name}"
			if hasattr(doc, "due_date"):
				description += f" (Due: {doc.due_date})"

		elif self.reference_doctype == "Sales Order":
			if hasattr(doc, "customer_name"):
				description = f"Order payment for {doc.customer_name}"
			if hasattr(doc, "transaction_date"):
				description += f" (Date: {doc.transaction_date})"

		elif self.reference_doctype == "Quotation":
			description = (
				f"Quotation {self.reference_docname} - {doc.party_name if hasattr(doc, 'party_name') else ''}"
			)

		return description[:200]

	def validate_amount(self):
		"""Validate minimum amount for currency"""
		if not self.amount or not self.currency:
			return

		if self.amount <= 0:
			frappe.throw(_("Amount must be greater than zero"))

	def validate_expiry(self):
		"""Check if request has expired"""
		if self.expiry_date and self.expiry_date < now():
			if self.status not in ["Succeeded", "Completed"]:
				self.status = "Canceled"

	def set_amount_in_cents(self):
		"""Convert amount to cents for Stripe"""
		if self.amount and self.currency:
			# Most currencies use 2 decimal places
			self.amount_in_cents = cint(flt(self.amount) * 100)

	def validate_stripe_settings(self):
		"""Validate Stripe settings and fetch gateway info"""
		if self.stripe_settings:
			settings = frappe.get_doc("Stripe Settings", self.stripe_settings)
			self.payment_gateway = settings.gateway_name

	def before_save(self):
		"""Set updated timestamp"""
		self.updated_at = now()

	def on_submit(self):
		"""When Stripe Request is submitted, initiate payment and create payment link"""
		if self.status == "Draft":
			self.initiate_payment()

		# Create payment link and log
		payment_url = self.get_payment_url()

		# Add comment to reference document
		if self.reference_doctype and self.reference_docname:
			self.add_comment_to_reference(payment_url)

		frappe.msgprint(
			_("Stripe Request {0} submitted successfully.<br>Payment URL: {1}").format(
				self.name, f"<a href='{payment_url}' target='_blank'>{payment_url}</a>"
			),
			title=_("Payment Request Created"),
			indicator="green",
		)

	def add_comment_to_reference(self, payment_url):
		"""Add comment to reference document about payment request"""
		try:
			comment = frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": self.reference_doctype,
					"reference_name": self.reference_docname,
					"content": f"Stripe payment request created: {self.name}<br>Amount: {fmt_money(self.amount, currency=self.currency)}<br>Payment link: {payment_url}",
				}
			)
			comment.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Failed to add comment to reference")

	def initiate_payment(self):
		"""Create Stripe Payment Intent"""
		if not self.stripe_settings:
			frappe.throw(_("Stripe Settings is required"))

		# Don't recreate if already exists
		if self.stripe_client_secret:
			return {
				"client_secret": self.stripe_client_secret,
				"payment_intent_id": self.stripe_payment_intent_id,
				"status": "already_initiated",
			}

		try:
			settings = frappe.get_doc("Stripe Settings", self.stripe_settings)
			stripe.api_key = settings.get_password(fieldname="secret_key", raise_exception=False)

			# Prepare metadata
			metadata = {
				"stripe_request_id": self.name,
				"reference_doctype": self.reference_doctype or "",
				"reference_docname": self.reference_docname or "",
				"integration_request_service": "Stripe",
			}

			# Add custom metadata
			if self.custom_metadata:
				try:
					custom_meta = json.loads(self.custom_metadata)
					metadata.update(custom_meta)
				except:
					pass

			# Add table metadata
			if self.payment_metadata:
				for row in self.payment_metadata:
					metadata[row.meta_key] = row.meta_value

			# Create payment intent
			intent = stripe.PaymentIntent.create(
				amount=self.amount_in_cents,
				currency=self.currency.lower(),
				metadata=metadata,
				receipt_email=self.payer_email,
				description=self.description or self.title,
				confirm=False,
				capture_method="automatic",
				setup_future_usage="off_session" if self.reference_doctype else None,
			)

			self.stripe_payment_intent_id = intent.id
			self.stripe_client_secret = intent.client_secret
			self.status = "Initiated"
			self.save(ignore_permissions=True)

			# Create integration request log
			self.create_integration_request("Initiated", intent)

			# Send notification email if payer email exists
			if self.payer_email:
				self.send_payment_notification()

			return {
				"client_secret": intent.client_secret,
				"payment_intent_id": intent.id,
				"status": "success",
			}

		except stripe.error.StripeError as e:
			self.handle_stripe_error(e)
			frappe.throw(_("Failed to create payment: {0}").format(str(e)))
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Stripe Initiation Error")
			self.status = "Failed"
			self.failure_message = str(e)
			self.save(ignore_permissions=True)
			frappe.throw(_("Failed to create payment: {0}").format(str(e)))

	def send_payment_notification(self):
		"""Send email notification to payer with payment link"""
		try:
			payment_url = self.get_payment_url()

			email_template = f"""
			<h3>Payment Request: {self.title}</h3>
			<p>Dear {self.payer_name},</p>
			<p>Please click the link below to complete your payment:</p>
			<p><a href="{payment_url}" style="background-color: #4F46E5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Pay {fmt_money(self.amount, currency=self.currency)}</a></p>
			<p>Or copy this link: {payment_url}</p>
			<p>Reference: {self.name}</p>
			<p>Description: {self.description}</p>
			<p>This payment link will expire on {self.expiry_date if self.expiry_date else "7 days from now"}.</p>
			<br>
			<p>Thank you for your business!</p>
			"""

			frappe.sendmail(
				recipients=[self.payer_email],
				subject=f"Payment Request: {self.title} - {fmt_money(self.amount, currency=self.currency)}",
				message=email_template,
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Failed to send payment notification")

	def confirm_payment(self, payment_method_id):
		"""Confirm payment with Stripe"""
		try:
			settings = frappe.get_doc("Stripe Settings", self.stripe_settings)
			stripe.api_key = settings.get_password(fieldname="secret_key", raise_exception=False)

			# Confirm the payment intent
			intent = stripe.PaymentIntent.confirm(
				self.stripe_payment_intent_id,
				payment_method=payment_method_id,
				return_url=get_url(self.redirect_url or "/payment-success"),
			)

			self.stripe_payment_method_id = payment_method_id
			self.payment_response = json.dumps(intent.to_dict(), indent=2)

			# Update status based on intent status
			status_map = {
				"requires_action": "Requires Action",
				"requires_confirmation": "Requires Confirmation",
				"requires_payment_method": "Requires Payment Method",
				"requires_capture": "Requires Capture",
				"succeeded": "Succeeded",
				"processing": "Processing",
			}

			self.status = status_map.get(intent.status, "Processing")

			if intent.status == "succeeded":
				self.paid_at = now()
				self.handle_successful_payment(intent)
			elif intent.status in ["requires_action", "requires_confirmation"]:
				self.handle_action_required(intent)

			self.save(ignore_permissions=True)

			# Update integration request
			self.update_integration_request(self.status, intent)

			return {
				"status": self.status.lower().replace(" ", "_"),
				"payment_intent": intent.to_dict(),
				"client_secret": intent.client_secret if hasattr(intent, "client_secret") else None,
			}

		except stripe.error.CardError as e:
			return self.handle_card_error(e)
		except stripe.error.StripeError as e:
			return self.handle_stripe_error(e)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Stripe Confirmation Error")
			self.status = "Failed"
			self.failure_message = str(e)
			self.save(ignore_permissions=True)
			return {"status": "error", "error": str(e)}

	def handle_successful_payment(self, intent):
		"""Handle successful payment"""
		self.paid_at = now()

		# Update reference document if it has a payment status field
		if self.reference_doctype and self.reference_docname:
			try:
				doc = frappe.get_doc(self.reference_doctype, self.reference_docname)

				# Call payment authorized method if exists
				if hasattr(doc, "on_payment_authorized"):
					doc.run_method("on_payment_authorized", "Completed")

				# Update payment status if field exists
				if hasattr(doc, "payment_status"):
					doc.db_set("payment_status", "Paid")

				# Add comment about successful payment
				comment = frappe.get_doc(
					{
						"doctype": "Comment",
						"comment_type": "Info",
						"reference_doctype": self.reference_doctype,
						"reference_name": self.reference_docname,
						"content": f"Payment of {fmt_money(self.amount, currency=self.currency)} received via Stripe. Transaction ID: {self.stripe_payment_intent_id}",
					}
				)
				comment.insert(ignore_permissions=True)

			except Exception:
				frappe.log_error(frappe.get_traceback(), "Payment Callback Error")

	def handle_action_required(self, intent):
		"""Handle payment requiring additional action"""
		self.payment_response = json.dumps(
			{"action_required": True, "next_action": intent.next_action.type if intent.next_action else None},
			indent=2,
		)

	def handle_card_error(self, error):
		"""Handle Stripe card errors"""
		error_message = error.user_message or str(error)
		self.status = "Failed"
		self.failure_message = error_message
		self.payment_response = json.dumps(
			{"error_type": "card_error", "error_code": error.code, "error_message": error_message}, indent=2
		)
		self.save(ignore_permissions=True)

		return {
			"status": "error",
			"error": error_message,
			"error_type": "card_error",
			"error_code": error.code,
		}

	def handle_stripe_error(self, error):
		"""Handle general Stripe errors"""
		error_message = str(error)
		self.status = "Failed"
		self.failure_message = error_message
		self.payment_response = json.dumps(
			{"error_type": "stripe_error", "error_message": error_message}, indent=2
		)
		self.save(ignore_permissions=True)

		frappe.log_error(
			title=f"Stripe Error - {self.name}", message=f"{error}\n\nTraceback: {frappe.get_traceback()}"
		)

		return {"status": "error", "error": error_message, "error_type": "stripe_error"}

	def get_payment_url(self):
		"""Generate unique payment URL"""
		if not self.name:
			return None
		return get_url(f"/stripe?request_id={self.name}")

	def create_integration_request(self, status, intent):
		"""Create integration request log"""
		try:
			# Map Stripe status to Integration Request status
			status_map = {
				"Initiated": "Queued",
				"Processing": "Queued",
				"Requires Action": "Queued",
				"Succeeded": "Completed",
				"Completed": "Completed",
				"Failed": "Failed",
				"Canceled": "Cancelled",
			}

			integration_status = status_map.get(status, "Queued")

			request_data = {
				"doctype": "Integration Request",
				"integration_request_service": "Stripe",
				"reference_doctype": self.doctype,
				"reference_docname": self.name,
				"data": json.dumps(
					{
						"amount": self.amount,
						"currency": self.currency,
						"payment_intent_id": intent.id,
						"status": status,
					}
				),
				"status": integration_status,  # Use mapped status
			}

			integration_request = frappe.get_doc(request_data)
			integration_request.insert(ignore_permissions=True)

		except Exception:
			frappe.log_error(frappe.get_traceback(), "Integration Request Creation Error")

	def update_integration_request(self, status, intent):
		"""Update integration request log"""
		try:
			# Map Stripe status to Integration Request status
			status_map = {
				"Initiated": "Queued",
				"Processing": "Queued",
				"Requires Action": "Queued",
				"Requires Confirmation": "Queued",
				"Requires Payment Method": "Queued",
				"Requires Capture": "Queued",
				"Succeeded": "Completed",
				"Completed": "Completed",
				"Partially Paid": "Completed",
				"Failed": "Failed",
				"Canceled": "Cancelled",
				"Refunded": "Completed",
				"Disputed": "Failed",
			}

			integration_status = status_map.get(status, "Queued")

			integration_requests = frappe.get_all(
				"Integration Request",
				filters={
					"reference_doctype": self.doctype,
					"reference_docname": self.name,
					"integration_request_service": "Stripe",
				},
				order_by="creation desc",
				limit=1,
			)

			if integration_requests:
				integration_request = frappe.get_doc("Integration Request", integration_requests[0].name)
				integration_request.status = integration_status  # Use mapped status
				integration_request.output = json.dumps(intent.to_dict(), indent=2)
				integration_request.save(ignore_permissions=True)

		except Exception:
			frappe.log_error(frappe.get_traceback(), "Integration Request Update Error")


# API Methods


@frappe.whitelist(allow_guest=True)
def create_stripe_request(data):
	"""Create a new Stripe Request"""
	data = frappe.parse_json(data) if isinstance(data, str) else data

	request = frappe.get_doc(
		{
			"doctype": "Stripe Request",
			"stripe_settings": data.get("stripe_settings"),
			"amount": data.get("amount"),
			"currency": data.get("currency", "USD"),
			"title": data.get("title", "Payment Request"),
			"description": data.get("description"),
			"reference_doctype": data.get("reference_doctype"),
			"reference_docname": data.get("reference_docname"),
			"payer_name": data.get("payer_name"),
			"payer_email": data.get("payer_email"),
			"payer_phone": data.get("payer_phone"),
			"redirect_url": data.get("redirect_url", "/payment-success"),
			"redirect_message": data.get("redirect_message"),
			"expiry_date": data.get("expiry_date"),
			"custom_metadata": json.dumps(data.get("custom_metadata", {}))
			if data.get("custom_metadata")
			else None,
		}
	)

	request.insert()
	request.submit()  # Auto-submit to trigger payment creation

	return {
		"stripe_request_id": request.name,
		"client_secret": request.stripe_client_secret,
		"payment_url": request.get_payment_url(),
		"status": "success",
	}


@frappe.whitelist(allow_guest=True)
def get_stripe_request(request_id):
	"""Get Stripe Request details (public)"""
	request = frappe.get_doc("Stripe Request", request_id)

	# Don't expose sensitive data
	return {
		"name": request.name,
		"title": request.title,
		"description": request.description,
		"amount": request.amount,
		"currency": request.currency,
		"payer_name": request.payer_name,
		"payer_email": request.payer_email,
		"status": request.status,
		"client_secret": request.stripe_client_secret if request.status != "Succeeded" else None,
		"expired": request.expiry_date and request.expiry_date < now(),
		"redirect_url": request.redirect_url,
		"redirect_message": request.redirect_message,
	}


@frappe.whitelist(allow_guest=True)
def confirm_stripe_payment(request_id, payment_method_id=None, payment_intent_id=None):
	"""Confirm Stripe payment"""
	request = frappe.get_doc("Stripe Request", request_id)

	if payment_method_id:
		result = request.confirm_payment(payment_method_id)
	else:
		result = {"status": "error", "error": "No payment method provided"}

	return result


@frappe.whitelist()
def create_from_reference(reference_doctype, reference_docname, stripe_settings=None):
	"""Helper method to create a Stripe Request from a reference document"""
	# Get default stripe settings if not provided
	if not stripe_settings:
		stripe_settings = frappe.get_value("Stripe Settings", {"enabled": 1}, "name")
		if not stripe_settings:
			stripe_settings = frappe.get_all("Stripe Settings", limit=1)[0].name

	# Create minimal request - auto-fetch will handle the rest
	request = frappe.get_doc(
		{
			"doctype": "Stripe Request",
			"stripe_settings": stripe_settings,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"title": f"Payment for {reference_doctype} {reference_docname}",
			"expiry_date": add_days(frappe.utils.nowdate(), 7),
		}
	)

	request.insert()
	request.submit()

	return {
		"stripe_request_id": request.name,
		"payment_url": request.get_payment_url(),
		"amount": request.amount,
		"currency": request.currency,
	}
