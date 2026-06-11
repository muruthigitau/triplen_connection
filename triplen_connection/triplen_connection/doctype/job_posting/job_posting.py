# Copyright (c) 2026, David Gitau and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class JobPosting(Document):
	def after_insert(self):
		self.send_job_alert_to_active_caregivers()

	def send_job_alert_to_active_caregivers(self):
		if not frappe.db.exists("Email Template", "Job Posting"):
			frappe.throw(_("Email Template 'Job Posting' not found"))

		email_template = frappe.get_doc("Email Template", "Job Posting")
		content = email_template.response_html or email_template.response

		active_memberships = frappe.get_all(
			"Caregiver Membership", filters={"status": "Active"}, fields=["user"]
		)

		unique_emails = set()
		for membership in active_memberships:
			user = frappe.get_doc("User", membership.user)
			if user.enabled and user.email:
				unique_emails.add(user.email)

		for email in unique_emails:
			args = {"doc": self, "recipient_email": email}

			message = frappe.render_template(content, args)

			frappe.sendmail(
				recipients=email,
				subject=email_template.subject or _("New Job Opening: {0}").format(self.title),
				message=message,
				now=True,
			)
