# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Certification(Document):
	def validate(self):
		bill = frappe.db.get_value(
			"Client RA Bill",
			self.client_ra_bill,
			["docstatus", "current_value", "company", "project", "customer"],
			as_dict=True,
		)
		if bill.docstatus != 1:
			frappe.throw(_("Client RA Bill {0} is not submitted").format(self.client_ra_bill))
		self.company, self.project, self.customer = bill.company, bill.project, bill.customer
		self.submitted_amount = bill.current_value
		if flt(self.certified_amount) < 0:
			frappe.throw(_("Certified amount cannot be negative"))
		self.difference = flt(self.submitted_amount) - flt(self.certified_amount)
		self.difference_percent = (
			self.difference / flt(self.submitted_amount) * 100 if flt(self.submitted_amount) else 0
		)
		if abs(self.difference) > 0.5 and not self.reason_for_difference:
			frappe.throw(_("Record the reason the certified amount differs from the bill"))
		if self.difference < -0.5:
			frappe.msgprint(_("The client certified more than was billed"), indicator="orange", alert=True)

	def before_submit(self):
		other = frappe.db.get_value(
			"Certification", {"client_ra_bill": self.client_ra_bill, "docstatus": 1, "name": ["!=", self.name]}
		)
		if other:
			frappe.throw(_("RA bill {0} is already certified in {1}").format(self.client_ra_bill, other))

	def on_submit(self):
		status = frappe.db.get_value("Client RA Bill", self.client_ra_bill, "status")
		values = {"certified_amount": self.certified_amount, "certification": self.name}
		if status == "Submitted":
			values["status"] = "Certified"
		frappe.db.set_value("Client RA Bill", self.client_ra_bill, values)

	def on_cancel(self):
		status = frappe.db.get_value("Client RA Bill", self.client_ra_bill, "status")
		values = {"certified_amount": 0, "certification": None}
		if status == "Certified":
			values["status"] = "Submitted"
		frappe.db.set_value("Client RA Bill", self.client_ra_bill, values)
