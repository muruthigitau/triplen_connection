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
	def after_insert(self):
		url = self.get_payment_url()
		self.route = url
		self.save(ignore_permissions=True)

	def get_payment_url(self):
		"""Generate secure payment URL for this request"""
		base_url = frappe.utils.get_url()

		payment_url = f"{base_url}/stripe?request_id={self.name}"

		return payment_url
