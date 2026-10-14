# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sanvidhi_epc.utils.permissions import APPROVER_ROLES, user_has_any
from sanvidhi_epc.utils.progress import update_boq_executed, update_work_order_measured


class MeasurementBook(Document):
	def validate(self):
		self.validate_parents()
		self.validate_variation()
		self.set_quantities()
		self.validate_limits()

	def validate_parents(self):
		if frappe.db.get_value("BOQ", self.boq, "docstatus") != 1:
			frappe.throw(_("BOQ {0} is not submitted").format(self.boq))
		if self.mb_type == "Contractor":
			wo = frappe.db.get_value(
				"Contractor Work Order",
				self.contractor_work_order,
				["docstatus", "status", "boq", "project", "supplier"],
				as_dict=True,
			)
			if not wo or wo.docstatus != 1:
				frappe.throw(_("Contractor Work Order {0} is not submitted").format(self.contractor_work_order))
			if wo.status == "Closed":
				frappe.throw(_("Contractor Work Order {0} is closed").format(self.contractor_work_order))
			self.boq, self.project, self.supplier = wo.boq, wo.project, wo.supplier
		else:
			self.contractor_work_order = None
			self.supplier = None
			self.project = frappe.db.get_value("BOQ", self.boq, "project")
		if self.period_from and self.period_to and self.period_to < self.period_from:
			frappe.throw(_("Period To cannot be before Period From"))

	def validate_variation(self):
		before = self.get_doc_before_save()
		changed = self.allow_excess and (not before or not before.allow_excess)
		if changed and not user_has_any(APPROVER_ROLES):
			frappe.throw(_("Only an EPC Project Manager or EPC MD can approve a variation"))
		if self.allow_excess and not self.variation_reference:
			frappe.throw(_("Enter the variation reference"))

	def _limit_rows(self):
		"""BOQ Ref -> the row this measurement counts against (work order line or BOQ line)."""
		if self.mb_type == "Contractor":
			return {
				r.boq_ref: r
				for r in frappe.get_all(
					"Contractor Work Order Item",
					filters={"parent": self.contractor_work_order},
					fields=["name", "boq_ref", "boq_item", "description", "uom", "qty"],
				)
			}
		return {
			r.boq_ref: r
			for r in frappe.get_all(
				"BOQ Item",
				filters={"parent": self.boq, "parenttype": "BOQ"},
				fields=["name", "boq_ref", "name as boq_item", "description", "uom", "qty"],
			)
		}

	def set_quantities(self):
		limits = self._limit_rows()
		for row in self.items:
			ref = limits.get(row.boq_ref)
			if not ref:
				source = self.contractor_work_order if self.mb_type == "Contractor" else self.boq
				frappe.throw(_("Row {0}: BOQ Ref {1} is not in {2}").format(row.idx, row.boq_ref, source))
			row.boq_item = ref.boq_item
			row.work_order_item = ref.name if self.mb_type == "Contractor" else None
			row.description = row.description or ref.description
			row.uom = row.uom or ref.uom
			dims = [flt(row.length), flt(row.breadth), flt(row.depth)]
			if any(dims):
				qty = flt(row.nos) or 1
				for d in dims:
					qty *= d or 1
				row.qty = qty
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: quantity must be more than zero").format(row.idx))

	def validate_limits(self):
		"""Measured to date may not pass the order (or BOQ) quantity without an approved variation."""
		if self.allow_excess:
			return
		limits = self._limit_rows()
		key = "work_order_item" if self.mb_type == "Contractor" else "boq_item"
		parent_filter = (
			("p.contractor_work_order", self.contractor_work_order)
			if self.mb_type == "Contractor"
			else ("p.boq", self.boq)
		)
		earlier = {
			r.k: flt(r.qty)
			for r in frappe.db.sql(
				f"""select c.{key} as k, sum(c.qty) as qty from `tabMeasurement Book Item` c
				join `tabMeasurement Book` p on p.name = c.parent
				where p.docstatus = 1 and p.mb_type = %s and {parent_filter[0]} = %s and p.name != %s
				group by c.{key}""",
				(self.mb_type, parent_filter[1], self.name),
				as_dict=True,
			)
		}
		this = {}
		for row in self.items:
			this[row.get(key)] = this.get(row.get(key), 0) + flt(row.qty)
		for ref in limits.values():
			k = ref.name if self.mb_type == "Contractor" else ref.boq_item
			total = earlier.get(k, 0) + this.get(k, 0)
			if this.get(k) and total > flt(ref.qty) + 1e-6:
				frappe.throw(
					_("BOQ Ref {0}: measured to date {1} would exceed the {2} quantity {3}. Record an approved variation to go above it.").format(
						frappe.bold(ref.boq_ref),
						total,
						_("work order") if self.mb_type == "Contractor" else _("BOQ"),
						ref.qty,
					),
					title=_("Quantity above limit"),
				)

	def before_submit(self):
		self.checked_by = frappe.session.user

	def on_submit(self):
		self.update_parents()

	def before_cancel(self):
		if self.billing_status == "Billed":
			frappe.throw(_("Cancel RA bill {0} first").format(frappe.bold(self.ra_bill)))

	def on_cancel(self):
		self.update_parents()

	def update_parents(self):
		if self.mb_type == "Contractor":
			update_work_order_measured(self.contractor_work_order)
		else:
			update_boq_executed(self.boq)
