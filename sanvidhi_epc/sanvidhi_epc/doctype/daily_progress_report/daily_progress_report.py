# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today


class DailyProgressReport(Document):
	def validate(self):
		if getdate(self.report_date) > getdate(today()):
			frappe.throw(_("A progress report cannot be dated in the future"))
		other = frappe.db.get_value(
			"Daily Progress Report",
			{
				"project": self.project,
				"report_date": self.report_date,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if other:
			frappe.throw(
				_("{0} already has a progress report for {1}: {2}").format(
					self.project, frappe.format(self.report_date, {"fieldtype": "Date"}), frappe.bold(other)
				)
			)
		self.total_labour = sum(cint(r.count) for r in self.labour)
		if not self.work_done and not self.hindrances:
			frappe.throw(_("Record the work done, or the hindrance that stopped work"))
