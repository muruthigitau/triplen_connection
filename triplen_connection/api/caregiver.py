import frappe
from frappe import _

from triplen_connection.api.auth import get_frontend_url
from triplen_connection.triplen_connection.doctype.caregiver_membership.caregiver_membership import (
	get_payment_url,
)


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
	redirect_to = f"{get_frontend_url().rstrip('/')}/dashboard"

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
		"address": user_doc.custom_address or "",
		"experience_years": user_doc.custom_experience_years or "",
		"skills": user_doc.custom_skills or [],
		"availability": user_doc.custom_availability or "",
		"bio": user_doc.custom_bio or "",
		"certifications": frappe.db.get_all(
			"Caregiver Certification",
			filters={"user": user},
			fields=["name", "certification_name", "certification_file", "upload_date"],
		),
	}

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
	if profile_data.get("address"):
		user_doc.custom_address = profile_data["address"]
	if profile_data.get("experience_years"):
		user_doc.custom_experience_years = profile_data["experience_years"]
	if profile_data.get("skills"):
		user_doc.custom_skills = profile_data["skills"]
	if profile_data.get("availability"):
		user_doc.custom_availability = profile_data["availability"]
	if profile_data.get("bio"):
		user_doc.custom_bio = profile_data["bio"]

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
