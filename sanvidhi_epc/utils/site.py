import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from sanvidhi_epc.utils.settings import get_settings


def validate_material_request(doc, method=None):
	"""Workflow 8 (optional): no new material request for a site until yesterday's DPR is submitted.

	A project with no DPR at all yet (a new site) is not held back.
	"""
	if not get_settings().enforce_dpr_before_material_request or doc.docstatus != 0:
		return
	yesterday = add_days(getdate(doc.transaction_date or today()), -1)
	projects = {row.project for row in doc.items if row.get("project")}
	for project in projects:
		if not frappe.db.exists("Daily Progress Report", {"project": project, "docstatus": 1}):
			continue
		if not frappe.db.exists(
			"Daily Progress Report", {"project": project, "report_date": yesterday, "docstatus": 1}
		):
			frappe.throw(
				_("Submit the Daily Progress Report of {0} for {1} before raising a material request").format(
					frappe.bold(project), frappe.format(yesterday, {"fieldtype": "Date"})
				),
				title=_("DPR pending"),
			)
