import hashlib
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_to_date, format_datetime, get_url, now_datetime, validate_email_address
from frappe.utils.password import update_password as frappe_update_password


@frappe.whitelist(allow_guest=True)
def signup(email, first_name, last_name, phone=None, sex=None):
	if not email or not first_name or not last_name:
		frappe.throw(_("Missing required fields."))

	validate_email_address(email, throw=True)

	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."), frappe.DuplicateEntryError)

	frontend_url = get_frontend_url()

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"last_name": last_name,
			"mobile_no": phone,
			"gender": sex,
			"send_welcome_email": 0,
			"enabled": 1,
			"user_type": "System User",
			"roles": [{"role": "Customer"}],
		}
	)

	user.flags.ignore_permissions = True
	user.insert(ignore_permissions=True)

	reset_key = frappe.generate_hash()
	hashed_key = hashlib.sha256(reset_key.encode()).hexdigest()

	frappe.db.set_value(
		"User",
		user.name,
		{"reset_password_key": hashed_key, "last_reset_password_key_generated_on": now_datetime()},
	)

	frappe.db.commit()

	send_custom_welcome_email(user, reset_key, frontend_url)

	return {"status": "Success", "message": _("Check your email to set your password.")}


@frappe.whitelist(allow_guest=True)
def forgot_password(email):
	if not email:
		frappe.throw(_("Email is required."))

	if not frappe.db.exists("User", email):
		return {"status": "Success", "message": _("If the email exists, a reset link has been sent.")}

	user = frappe.get_doc("User", email)

	if not user.enabled:
		frappe.throw(_("This account is disabled."))

	reset_key = frappe.generate_hash()
	hashed_key = hashlib.sha256(reset_key.encode()).hexdigest()

	frappe.db.set_value(
		"User",
		user.name,
		{"reset_password_key": hashed_key, "last_reset_password_key_generated_on": now_datetime()},
	)

	frappe.db.commit()  # ✅ ensure saved

	send_password_reset_email(user, reset_key, get_frontend_url())

	return {"status": "Success", "message": _("Password reset link has been sent to your email.")}


@frappe.whitelist(allow_guest=True)
def update_password_with_key(key, new_password, confirm_password):

	if not key:
		frappe.throw(_("Reset key is missing."))

	if not new_password:
		frappe.throw(_("New password is required."))

	if not confirm_password:
		frappe.throw(_("Please confirm your password."))

	if new_password != confirm_password:
		frappe.throw(_("Passwords do not match."))

	hashed_key = hashlib.sha256(key.encode()).hexdigest()

	user_name = frappe.db.get_value("User", {"reset_password_key": hashed_key}, "name")

	if not user_name:
		frappe.throw(_("Invalid or expired reset link."))

	last_generated = frappe.db.get_value("User", user_name, "last_reset_password_key_generated_on")

	if last_generated:
		expiry_time = add_to_date(last_generated, hours=24)
		if now_datetime() > expiry_time:
			frappe.throw(_("Reset link has expired."))

	frappe_update_password(user_name, new_password)

	frappe.db.set_value(
		"User", user_name, {"reset_password_key": "", "last_password_reset_date": now_datetime()}
	)

	frappe.db.commit()

	try:
		frappe.local.login_manager.login_as(user_name)
	except Exception:
		pass

	return {
		"status": "Success",
		"message": _("Password updated successfully."),
		"redirect_url": get_frontend_url() + "/dashboard",
	}


@frappe.whitelist(allow_guest=True)
def validate_reset_key(key):

	if not key:
		return {"valid": False, "message": _("Missing key.")}

	hashed_key = hashlib.sha256(key.encode()).hexdigest()

	user_name = frappe.db.get_value("User", {"reset_password_key": hashed_key}, "name")

	if not user_name:
		return {"valid": False, "message": _("Invalid key.")}

	last_generated = frappe.db.get_value("User", user_name, "last_reset_password_key_generated_on")

	if last_generated:
		expiry_time = add_to_date(last_generated, hours=24)
		if now_datetime() > expiry_time:
			return {"valid": False, "message": _("Key expired.")}

	return {"valid": True, "message": _("Valid key.")}


def get_frontend_url():
	referer = frappe.request.headers.get("Referer")
	if referer:
		parsed_url = urlparse(referer)
		return f"{parsed_url.scheme}://{parsed_url.netloc}"
	return frappe.conf.get("frontend_url") or "http://localhost:3000"


def send_password_reset_email(user, reset_key, frontend_url):
	template_name = "Password Reset Email"
	if not frappe.db.exists("Email Template", template_name):
		return

	doc = frappe.get_doc("Email Template", template_name)
	content = doc.response_html or doc.response

	reset_link = f"{frontend_url}/reset-password?key={reset_key}"

	args = {
		"first_name": user.first_name,
		"last_name": user.last_name,
		"email": user.email,
		"reset_link": reset_link,
		"site_url": frontend_url,
		"requested_time": format_datetime(now_datetime()),
	}

	message = frappe.render_template(content, args)

	frappe.sendmail(
		recipients=user.email,
		subject=doc.subject or _("Password Reset"),
		message=message,
		now=True,
	)


def send_custom_welcome_email(user, reset_key, frontend_url):
	template_name = "Welcome Email"
	if not frappe.db.exists("Email Template", template_name):
		return

	doc = frappe.get_doc("Email Template", template_name)
	content = doc.response_html or doc.response

	reset_link = f"{frontend_url}/reset-password?key={reset_key}"

	args = {
		"first_name": user.first_name,
		"last_name": user.last_name,
		"email": user.email,
		"reset_link": reset_link,
		"site_url": frontend_url,
		"created_time": format_datetime(now_datetime()),
	}

	message = frappe.render_template(content, args)

	frappe.sendmail(
		recipients=user.email,
		subject=doc.subject or _("Welcome"),
		message=message,
		now=True,
	)
