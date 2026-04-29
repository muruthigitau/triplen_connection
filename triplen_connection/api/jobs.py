# triplen_connection/api/jobs.py
import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def get_available_jobs():
	JobPosting = DocType("Job Posting")

	query = (
		frappe.qb.from_(JobPosting)
		.select(
			JobPosting.name.as_("id"),
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
			JobPosting.description,
			JobPosting.posted_date,
			JobPosting.status,
		)
		.where(JobPosting.status == "Active")
		.orderby(JobPosting.posted_date, order=frappe.qb.desc)
	)

	return query.run(as_dict=True)


@frappe.whitelist(allow_guest=True)
def get_job_details(job_id):
	JobPosting = DocType("Job Posting")
	JobRequirement = DocType("Job Requirement")

	job = (
		frappe.qb.from_(JobPosting)
		.select(
			JobPosting.name.as_("id"),
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
			JobPosting.description,
			JobPosting.posted_date,
			JobPosting.status,
		)
		.where(JobPosting.name == job_id)
	).run(as_dict=True)

	if job and len(job) > 0:
		requirements = (
			frappe.qb.from_(JobRequirement)
			.select(JobRequirement.requirement)
			.where(JobRequirement.parent == job_id)
		).run(as_dict=True)

		job[0]["requirements"] = [req.requirement for req in requirements]
		return job[0]

	return None


@frappe.whitelist(allow_guest=True)
def get_job_requirements(job_id):
	JobRequirement = DocType("Job Requirement")

	requirements = (
		frappe.qb.from_(JobRequirement)
		.select(JobRequirement.requirement)
		.where(JobRequirement.parent == job_id)
	).run(as_dict=True)

	return requirements


@frappe.whitelist(allow_guest=True)
def apply_for_job(job_id, message=""):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to apply for jobs"))

	JobApplication = DocType("Job Application")

	existing = (
		frappe.qb.from_(JobApplication)
		.select(JobApplication.name)
		.where((JobApplication.job_posting == job_id) & (JobApplication.user == user))
	).run()

	if existing:
		frappe.throw(_("You have already applied for this job"))

	application = frappe.get_doc(
		{
			"doctype": "Job Application",
			"job_posting": job_id,
			"user": user,
			"application_date": now_datetime(),
			"message": message,
			"status": "Pending",
			"docstatus": 0,
		}
	)
	application.insert(ignore_permissions=True)
	application.submit()

	return {"success": True, "message": "Application submitted successfully"}


@frappe.whitelist(allow_guest=True)
def get_applied_jobs():
	user = frappe.session.user

	if user == "Guest":
		return []

	JobApplication = DocType("Job Application")
	JobPosting = DocType("Job Posting")

	query = (
		frappe.qb.from_(JobApplication)
		.join(JobPosting)
		.on(JobApplication.job_posting == JobPosting.name)
		.select(
			JobApplication.name.as_("id"),
			JobApplication.job_posting,
			JobApplication.application_date,
			JobApplication.status,
			JobApplication.message,
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
		)
		.where((JobApplication.user == user) & (JobApplication.docstatus == 1))
		.orderby(JobApplication.application_date, order=frappe.qb.desc)
	)

	return query.run(as_dict=True)


@frappe.whitelist(allow_guest=True)
def save_job(job_id):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to save jobs"))

	SavedJob = DocType("Saved Job")

	existing = (
		frappe.qb.from_(SavedJob)
		.select(SavedJob.name)
		.where((SavedJob.job_posting == job_id) & (SavedJob.user == user))
	).run()

	if existing:
		frappe.db.delete("Saved Job", {"job_posting": job_id, "user": user})
		return {"success": True, "message": "Job removed from saved"}

	saved = frappe.get_doc({"doctype": "Saved Job", "job_posting": job_id, "user": user})
	saved.insert(ignore_permissions=True)

	return {"success": True, "message": "Job saved successfully"}


@frappe.whitelist(allow_guest=True)
def get_saved_jobs():
	user = frappe.session.user

	if user == "Guest":
		return []

	SavedJob = DocType("Saved Job")
	JobPosting = DocType("Job Posting")

	query = (
		frappe.qb.from_(SavedJob)
		.join(JobPosting)
		.on(SavedJob.job_posting == JobPosting.name)
		.select(
			JobPosting.name.as_("id"),
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
			JobPosting.description,
			JobPosting.status.as_("job_status"),
		)
		.where((SavedJob.user == user) & (JobPosting.status == "Active"))
		.orderby(SavedJob.creation, order=frappe.qb.desc)
	)

	return query.run(as_dict=True)


@frappe.whitelist(allow_guest=True)
def check_if_applied(job_id):
	user = frappe.session.user

	if user == "Guest":
		return {"applied": False}

	JobApplication = DocType("Job Application")

	applied = (
		frappe.qb.from_(JobApplication)
		.select(JobApplication.name)
		.where(
			(JobApplication.job_posting == job_id)
			& (JobApplication.user == user)
			& (JobApplication.docstatus == 1)
		)
	).run()

	return {"applied": bool(applied)}


@frappe.whitelist(allow_guest=True)
def check_if_saved(job_id):
	user = frappe.session.user

	if user == "Guest":
		return {"saved": False}

	SavedJob = DocType("Saved Job")

	saved = (
		frappe.qb.from_(SavedJob)
		.select(SavedJob.name)
		.where((SavedJob.job_posting == job_id) & (SavedJob.user == user))
	).run()

	return {"saved": bool(saved)}


@frappe.whitelist(allow_guest=True)
def update_application_status(application_id, status, feedback=None):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Permission denied"))

	allowed_statuses = ["Pending", "Reviewed", "Interview", "Hired", "Rejected"]
	if status not in allowed_statuses:
		frappe.throw(_("Invalid status"))

	application = frappe.get_doc("Job Application", application_id)

	if application.docstatus != 1:
		frappe.throw(_("Application not submitted"))

	application.status = status
	if feedback:
		application.feedback = feedback

	application.save(ignore_permissions=True)

	return {"success": True, "message": f"Application status updated to {status}"}


@frappe.whitelist(allow_guest=True)
def get_application_details(application_id):
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to view applications"))

	JobApplication = DocType("Job Application")
	JobPosting = DocType("Job Posting")

	query = (
		frappe.qb.from_(JobApplication)
		.join(JobPosting)
		.on(JobApplication.job_posting == JobPosting.name)
		.select(
			JobApplication.name.as_("id"),
			JobApplication.job_posting,
			JobApplication.application_date,
			JobApplication.status,
			JobApplication.message,
			JobApplication.feedback,
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
			JobPosting.description,
		)
		.where(
			(JobApplication.name == application_id)
			& (JobApplication.user == user)
			& (JobApplication.docstatus == 1)
		)
	)

	application = query.run(as_dict=True)

	if not application:
		frappe.throw(_("Application not found"))

	return application[0]


@frappe.whitelist(allow_guest=True)
def get_all_job_applications_for_admin():
	user = frappe.session.user

	if user == "Guest":
		frappe.throw(_("Please login to view applications"))

	# Check if user has admin role (optional - implement your own role check)
	user_roles = frappe.get_roles(user)
	if "System Manager" not in user_roles and "Administrator" not in user_roles:
		frappe.throw(_("Permission denied. Admin access required."))

	JobApplication = DocType("Job Application")
	JobPosting = DocType("Job Posting")

	query = (
		frappe.qb.from_(JobApplication)
		.join(JobPosting)
		.on(JobApplication.job_posting == JobPosting.name)
		.select(
			JobApplication.name.as_("id"),
			JobApplication.job_posting,
			JobApplication.user,
			JobApplication.application_date,
			JobApplication.status,
			JobApplication.message,
			JobApplication.feedback,
			JobPosting.title,
			JobPosting.location,
			JobPosting.pay,
			JobPosting.schedule,
		)
		.where(JobApplication.docstatus == 1)
		.orderby(JobApplication.application_date, order=frappe.qb.desc)
	)

	return query.run(as_dict=True)


@frappe.whitelist(allow_guest=True)
def get_job_count_by_status():
	user = frappe.session.user

	if user == "Guest":
		return {"total": 0, "active": 0, "filled": 0, "closed": 0}

	JobPosting = DocType("Job Posting")

	total = frappe.qb.from_(JobPosting).select(JobPosting.name).run()

	active = (frappe.qb.from_(JobPosting).select(JobPosting.name).where(JobPosting.status == "Active")).run()

	filled = (frappe.qb.from_(JobPosting).select(JobPosting.name).where(JobPosting.status == "Filled")).run()

	closed = (frappe.qb.from_(JobPosting).select(JobPosting.name).where(JobPosting.status == "Closed")).run()

	return {"total": len(total), "active": len(active), "filled": len(filled), "closed": len(closed)}
