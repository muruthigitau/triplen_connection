# triplen_connection/api/caregiver.py
import frappe
from frappe import _


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
