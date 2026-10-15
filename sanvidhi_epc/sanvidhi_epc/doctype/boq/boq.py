# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BOQ(Document):
	def before_insert(self):
		if self.amended_from:
			self.revision = (frappe.db.get_value("BOQ", self.amended_from, "revision") or 0) + 1

	def validate(self):
		self.validate_project()
		self.validate_items()
		self.set_totals()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_project(self):
		project = frappe.db.get_value("Project", self.project, ["company", "customer"], as_dict=True)
		if project.company and project.company != self.company:
			frappe.throw(_("Project {0} belongs to {1}").format(self.project, project.company))
		if not self.customer and project.customer:
			self.customer = project.customer

	def validate_items(self):
		seen = set()
		for row in self.items:
			if row.boq_ref in seen:
				frappe.throw(_("Row {0}: BOQ Ref {1} is repeated").format(row.idx, frappe.bold(row.boq_ref)))
			seen.add(row.boq_ref)
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: quantity must be more than zero").format(row.idx))
			row.amount = flt(row.qty) * flt(row.rate)
			row.cost_amount = flt(row.qty) * flt(row.cost_rate)

	def set_totals(self):
		self.total_contract_value = sum(flt(r.amount) for r in self.items)
		self.total_budgeted_cost = sum(flt(r.cost_amount) for r in self.items)
		self.planned_margin = self.total_contract_value - self.total_budgeted_cost
		self.planned_margin_percent = (
			self.planned_margin / self.total_contract_value * 100 if self.total_contract_value else 0
		)

	def before_submit(self):
		active = frappe.db.get_value(
			"BOQ", {"project": self.project, "docstatus": 1, "status": "Active", "name": ["!=", self.name]}
		)
		if active:
			frappe.throw(
				_("Project {0} already has an active BOQ {1}. Cancel and amend it to revise.").format(
					self.project, frappe.bold(active)
				)
			)
		self.status = "Active"

	def on_submit(self):
		# the BOQ's budgeted cost becomes the project's estimated cost
		frappe.db.set_value("Project", self.project, "estimated_costing", self.total_budgeted_cost)
		# a Task per BOQ line (plus the EPC template's stages on a new project), then progress and margin
		from sanvidhi_epc.utils.planning import refresh_actuals, sync_boq_tasks

		sync_boq_tasks(self)
		refresh_actuals(self.name)

	def before_cancel(self):
		for doctype in ("Contractor Work Order", "Client RA Bill", "Measurement Book"):
			used = frappe.db.get_value(doctype, {"boq": self.name, "docstatus": 1})
			if used:
				frappe.throw(_("Cancel {0} {1} first").format(_(doctype), frappe.bold(used)))

	def on_cancel(self):
		self.db_set("status", "Cancelled")


@frappe.whitelist()
def get_boq_items(boq, for_doctype=None):
	"""BOQ lines for the work order / measurement 'Get Items' buttons."""
	frappe.has_permission("BOQ", doc=boq, throw=True)
	if frappe.db.get_value("BOQ", boq, "docstatus") != 1:
		frappe.throw(_("BOQ {0} is not submitted").format(boq))
	return frappe.get_all(
		"BOQ Item",
		filters={"parent": boq, "parenttype": "BOQ"},
		fields=[
			"name",
			"boq_ref",
			"description",
			"uom",
			"qty",
			"rate",
			"cost_rate",
			"cost_head",
			"contracted_qty",
			"executed_qty",
			"billed_qty",
		],
		order_by="idx",
	)


@frappe.whitelist()
def refresh_progress(boq):
	"""Recompute task progress, the project's % complete and the margin to date (the 'Refresh Progress' button)."""
	frappe.has_permission("BOQ", "read", doc=boq, throw=True)
	if frappe.db.get_value("BOQ", boq, "docstatus") != 1:
		frappe.throw(_("BOQ {0} is not submitted").format(boq))
	from sanvidhi_epc.utils.planning import refresh_actuals, update_task_progress

	update_task_progress(boq)
	refresh_actuals(boq)
