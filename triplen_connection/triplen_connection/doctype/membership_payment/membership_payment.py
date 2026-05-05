# Copyright (c) 2026, David Gitau and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MembershipPayment(Document):
	def on_submit(self):
		self.update_membership_status()

	def on_update(self):
		if self.paid and self.docstatus == 0:
			self.update_membership_status()

	def update_membership_status(self):
		if self.paid and self.membership:
			frappe.db.set_value("Caregiver Membership", self.membership, "status", "Active")

			membership_user = frappe.get_value("Caregiver Membership", self.membership, "user")
			frappe.msgprint(f"Membership for {membership_user} has been activated.")

	def on_cancel(self):
		if self.membership:
			frappe.db.set_value("Caregiver Membership", self.membership, "status", "Pending")
