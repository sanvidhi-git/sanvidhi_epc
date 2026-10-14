# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DailyDigest(Document):
	@frappe.whitelist()
	def rebuild(self):
		from sanvidhi_epc.tasks.digest import build_digest

		return build_digest(self.digest_date).name

	@frappe.whitelist()
	def send_now(self):
		from sanvidhi_epc.tasks.digest import send_digest

		send_digest(self.name)
		return frappe.db.get_value("Daily Digest", self.name, "status")
