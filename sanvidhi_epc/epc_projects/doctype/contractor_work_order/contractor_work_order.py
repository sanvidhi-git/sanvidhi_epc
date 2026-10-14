# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sanvidhi_epc.utils.progress import update_boq_contracted
from sanvidhi_epc.utils.settings import get_settings


class ContractorWorkOrder(Document):
	def before_insert(self):
		settings = get_settings()
		if self.retention_percent is None:
			self.retention_percent = settings.default_retention_percent
		if self.tds_percent is None:
			self.tds_percent = settings.default_tds_percent
		if self.advance_recovery_percent is None:
			self.advance_recovery_percent = settings.default_advance_recovery_percent

	def validate(self):
		boq = frappe.db.get_value("BOQ", self.boq, ["project", "docstatus", "company"], as_dict=True)
		if boq.docstatus != 1:
			frappe.throw(_("BOQ {0} is not submitted").format(self.boq))
		if boq.project != self.project:
			frappe.throw(_("BOQ {0} belongs to project {1}").format(self.boq, boq.project))
		if self.end_date and self.start_date and self.end_date < self.start_date:
			frappe.throw(_("Completion date cannot be before the start date"))
		if flt(self.mobilisation_advance) and not flt(self.advance_recovery_percent):
			frappe.throw(_("Set the advance recovery % so the mobilisation advance is recovered from RA bills"))
		self.validate_items()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_items(self):
		boq_rows = {
			r.boq_ref: r
			for r in frappe.get_all(
				"BOQ Item",
				filters={"parent": self.boq, "parenttype": "BOQ"},
				fields=["name", "boq_ref", "description", "uom", "qty"],
			)
		}
		awarded_elsewhere = {
			r.boq_item: flt(r.qty)
			for r in frappe.db.sql(
				"""select c.boq_item, sum(c.qty) as qty from `tabContractor Work Order Item` c
				join `tabContractor Work Order` p on p.name = c.parent
				where p.docstatus = 1 and p.boq = %s and p.name != %s group by c.boq_item""",
				(self.boq, self.name),
				as_dict=True,
			)
		}
		seen = set()
		self.total_amount = 0
		for row in self.items:
			boq_row = boq_rows.get(row.boq_ref)
			if not boq_row:
				frappe.throw(_("Row {0}: BOQ Ref {1} is not in BOQ {2}").format(row.idx, row.boq_ref, self.boq))
			if row.boq_ref in seen:
				frappe.throw(_("Row {0}: BOQ Ref {1} is repeated").format(row.idx, row.boq_ref))
			seen.add(row.boq_ref)
			row.boq_item = boq_row.name
			row.description = row.description or boq_row.description
			row.uom = row.uom or boq_row.uom
			row.amount = flt(row.qty) * flt(row.rate)
			self.total_amount += row.amount
			# awarding more than the BOQ quantity is allowed (contingency) but flagged
			others = awarded_elsewhere.get(boq_row.name, 0)
			if others + flt(row.qty) > flt(boq_row.qty):
				frappe.msgprint(
					_("Row {0}: {1} awarded in all work orders exceeds the BOQ quantity {2}").format(
						row.idx, others + flt(row.qty), boq_row.qty
					),
					indicator="orange",
					alert=True,
				)

	def before_submit(self):
		self.status = "Open"

	def on_submit(self):
		update_boq_contracted(self.boq)

	def before_cancel(self):
		for doctype in ("Contractor RA Bill", "Measurement Book"):
			used = frappe.db.get_value(doctype, {"contractor_work_order": self.name, "docstatus": 1})
			if used:
				frappe.throw(_("Cancel {0} {1} first").format(_(doctype), frappe.bold(used)))

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		update_boq_contracted(self.boq)


@frappe.whitelist()
def close_work_order(name, status="Closed"):
	doc = frappe.get_doc("Contractor Work Order", name)
	doc.check_permission("submit")
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted work order can be closed"))
	doc.db_set("status", "Closed" if status == "Closed" else "Open")
	return doc.status


@frappe.whitelist()
def get_work_order_items(work_order):
	frappe.has_permission("Contractor Work Order", doc=work_order, throw=True)
	return frappe.get_all(
		"Contractor Work Order Item",
		filters={"parent": work_order},
		fields=["name", "boq_ref", "boq_item", "description", "uom", "qty", "rate", "measured_qty", "billed_qty"],
		order_by="idx",
	)
