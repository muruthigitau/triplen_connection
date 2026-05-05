import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate, nowdate
from frappe.website.utils import get_home_page

no_cache = 1


def get_context(context):
	"""Set context for stripe payment page"""
	context.no_cache = 1
	context.body_class = "stripe-payment-page"

	# Get request ID from URL query parameter
	request_id = frappe.form_dict.get("request_id")

	# Also check if it's in the path (for backward compatibility)
	if not request_id:
		path_parts = frappe.local.request.path.split("/")
		if len(path_parts) > 2 and path_parts[-2] == "stripe":
			request_id = path_parts[-1]

	if not request_id:
		frappe.redirect_to_message(
			_("Invalid Request"),
			_("No payment request found. Please check the URL and try again."),
			http_status_code=404,
		)
		context.is_valid = False
		return context

	try:
		# Fetch Stripe Request
		stripe_request = frappe.get_doc("Stripe Request", request_id)

		# Check if already completed
		if stripe_request.status in ["Succeeded", "Completed"]:
			context.payment_completed = True
			context.completion_message = _("This payment has already been processed successfully.")
			context.redirect_url = stripe_request.redirect_url or "/"
			context.is_valid = True
			return context

		# Check if expired - FIXED: Convert both to date objects for comparison
		if stripe_request.expiry_date:
			# Convert expiry_date to date object if it's a string
			expiry_date = stripe_request.expiry_date
			if isinstance(expiry_date, str):
				expiry_date = getdate(expiry_date)

			# Get current date as date object
			current_date = getdate(nowdate())

			if expiry_date < current_date:
				context.payment_expired = True
				context.expiry_message = _(
					"This payment link has expired. Please contact the merchant for assistance."
				)
				context.is_valid = True
				return context

		# Get Stripe Settings
		if not stripe_request.stripe_settings:
			frappe.log_error(f"Stripe Settings missing for request {request_id}", "Stripe Payment Error")
			context.payment_error = True
			context.error_message = _("Payment gateway configuration error. Please contact support.")
			context.is_valid = True
			return context

		stripe_settings = frappe.get_doc("Stripe Settings", stripe_request.stripe_settings)

		# Set all context variables
		context.stripe_request = stripe_request
		context.request_id = request_id
		context.client_secret = stripe_request.stripe_client_secret
		context.publishable_key = stripe_settings.publishable_key
		context.amount_display = fmt_money(stripe_request.amount, currency=stripe_request.currency)

		# Get company logo - with error handling
		context.company_logo = (
			stripe_settings.header_img
			or frappe.db.get_single_value("Website Settings", "brand_html")
			or "/assets/payments/images/payment-logo.png"
		)

		# Get company name - safely without causing errors
		context.company_name = "TripLen"
		try:
			# Try to get from Website Settings
			if frappe.db.exists("Website Settings", "Website Settings"):
				website_settings = frappe.get_doc("Website Settings")
				if hasattr(website_settings, "brand_name") and website_settings.brand_name:
					context.company_name = website_settings.brand_name
				elif hasattr(website_settings, "app_name") and website_settings.app_name:
					context.company_name = website_settings.app_name
		except Exception:
			# Fallback to System Settings
			try:
				context.company_name = frappe.db.get_single_value("System Settings", "app_name") or "TripLen"
			except:
				context.company_name = "TripLen"

		# Also try to get from Company doctype
		if context.company_name == "TripLen":
			try:
				companies = frappe.get_all("Company", limit=1)
				if companies:
					company = frappe.get_doc("Company", companies[0].name)
					context.company_name = company.company_name
			except:
				pass

		# Custom styling
		context.primary_color = getattr(stripe_settings, "primary_color", None) or "#635bff"
		context.secondary_color = getattr(stripe_settings, "secondary_color", None) or "#764ba2"

		context.is_valid = True

	except frappe.DoesNotExistError:
		context.is_valid = False
		context.error_title = _("Payment Request Not Found")
		context.error_message = _(
			"The payment request you're looking for does not exist or has been removed."
		)

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Stripe Payment Page Error")
		context.is_valid = False
		context.error_title = _("System Error")
		context.error_message = _("An error occurred while processing your request. Please try again later.")

	return context
