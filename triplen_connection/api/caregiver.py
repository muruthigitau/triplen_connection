import frappe
from frappe import _

from triplen_connection.api.auth import get_frontend_url
from triplen_connection.triplen_connection.doctype.caregiver_membership.caregiver_membership import (
	get_payment_url,
)

# API field name -> (custom fieldname on User, default value).
# These fields are optional: they only exist on sites where the caregiver
# customisations have been installed, so they are read and written defensively.
CAREGIVER_PROFILE_FIELDS = {
	"address": ("custom_address", ""),
	"experience_years": ("custom_experience_years", ""),
	"skills": ("custom_skills", []),
	"availability": ("custom_availability", ""),
	"bio": ("custom_bio", ""),
}


def _get_profile_field(user_doc, fieldname, default):
	"""Read an optional caregiver field from a User document.

	Args:
	    user_doc: User document being read.
	    fieldname: Custom fieldname to read.
	    default: Value returned when the field is not installed or empty.

	Returns:
	    The stored value, or ``default``.
	"""
	if not user_doc.meta.has_field(fieldname):
		return default

	return user_doc.get(fieldname) or default


def _set_profile_field(user_doc, fieldname, value):
	"""Write an optional caregiver field on a User document.

	Args:
	    user_doc: User document being updated.
	    fieldname: Custom fieldname to update.
	    value: Value to store. Falsy values are ignored, matching the
	        existing behaviour of the profile endpoint.
	"""
	if value and user_doc.meta.has_field(fieldname):
		setattr(user_doc, fieldname, value)


@frappe.whitelist()
def check_or_create_membership():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please login to manage memberships"))

	active_membership = frappe.db.get_value(
		"Caregiver Membership", {"user": user, "status": "Active", "docstatus": 1}, "name"
	)

	if active_membership:
		return {
			"status": "Active",
			"membership": active_membership,
			"message": _("You have an active membership."),
		}

	pending_membership = frappe.db.get_value(
		"Caregiver Membership", {"user": user, "status": "Pending", "docstatus": ["<", 2]}, "name"
	)

	if not pending_membership:
		membership_type = frappe.db.get_value(
			"Caregiver Membership Type", {}, "name", order_by="creation asc"
		)

		if not membership_type:
			frappe.throw(_("No Membership Types configured in the system."))

		m_type_doc = frappe.get_doc("Caregiver Membership Type", membership_type)

		doc = frappe.get_doc(
			{
				"doctype": "Caregiver Membership",
				"user": user,
				"membership_type": membership_type,
				"amount": m_type_doc.amount,
				"currency": m_type_doc.currency,
				"membership_duration": m_type_doc.membership_duration,
				"status": "Pending",
				"date_from": frappe.utils.now_datetime(),
			}
		)
		doc.insert(ignore_permissions=True)
		doc.flags.ignore_permissions = True
		doc.submit()
		pending_membership = doc.name

	m_type_name = frappe.db.get_value("Caregiver Membership", pending_membership, "membership_type")
	m_type = frappe.get_doc("Caregiver Membership Type", m_type_name)

	if not m_type.payment_methods:
		return {
			"status": "Pending",
			"membership": pending_membership,
			"message": _("Membership created, but no payment methods are available."),
		}

	method = m_type.payment_methods[0]
	redirect_to = "https://triplencaregiversconnection.com/dashboard"

	payment_url = get_payment_url(
		membership_name=pending_membership,
		gateway=method.payment_gateway,
		redirect_to=redirect_to,
	)

	return {
		"status": "Pending",
		"membership": pending_membership,
		"payment_url": payment_url,
		"gateway": method.payment_gateway,
	}


@frappe.whitelist()
def get_profile():
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to view profile"))

	user_doc = frappe.get_doc("User", user)

	profile = {
		"first_name": user_doc.first_name,
		"last_name": user_doc.last_name,
		"email": user_doc.email,
		"phone": user_doc.mobile_no or "",
		"certifications": frappe.db.get_all(
			"Caregiver Certification",
			filters={"user": user},
			fields=["name", "certification_name", "certification_file", "upload_date"],
		),
	}

	for api_field, (fieldname, default) in CAREGIVER_PROFILE_FIELDS.items():
		profile[api_field] = _get_profile_field(user_doc, fieldname, default)

	return profile


@frappe.whitelist()
def update_profile(profile_data):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to update profile"))

	user_doc = frappe.get_doc("User", user)

	if profile_data.get("first_name"):
		user_doc.first_name = profile_data["first_name"]
	if profile_data.get("last_name"):
		user_doc.last_name = profile_data["last_name"]
	if profile_data.get("phone"):
		user_doc.mobile_no = profile_data["phone"]

	for api_field, (fieldname, _default) in CAREGIVER_PROFILE_FIELDS.items():
		_set_profile_field(user_doc, fieldname, profile_data.get(api_field))

	user_doc.save(ignore_permissions=True)

	return {"success": True, "message": "Profile updated successfully"}


@frappe.whitelist()
def upload_certification(certification_name, certification_file):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to upload certifications"))

	cert = frappe.get_doc(
		{
			"doctype": "Caregiver Certification",
			"user": user,
			"certification_name": certification_name,
			"certification_file": certification_file,
			"upload_date": frappe.utils.now_datetime(),
			"status": "Pending",
		}
	)
	cert.insert(ignore_permissions=True)

	return {"success": True, "message": "Certification uploaded successfully"}


@frappe.whitelist()
def get_certifications():
	user = frappe.session.user

	if user == "Guest":
		return []

	return frappe.db.get_all(
		"Caregiver Certification",
		filters={"user": user},
		fields=["name", "certification_name", "certification_file", "upload_date", "status"],
		order_by="upload_date desc",
	)
