# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from sanvidhi_epc.utils.progress import mark_measurements, update_boq_billed
from sanvidhi_epc.utils.settings import get_settings, require


class ClientRABill(Document):
	def before_insert(self):
		self.bill_no = frappe.db.count("Client RA Bill", {"boq": self.boq, "docstatus": ["<", 2]}) + 1
		settings = get_settings()
		if self.retention_percent is None:
			self.retention_percent = settings.client_retention_percent

	def validate(self):
		boq = frappe.db.get_value("BOQ", self.boq, ["docstatus", "project", "company", "customer"], as_dict=True)
		if boq.docstatus != 1:
			frappe.throw(_("BOQ {0} is not submitted").format(self.boq))
		self.project, self.company = boq.project, boq.company
		self.customer = self.customer or boq.customer
		if not self.customer:
			frappe.throw(_("Set the client on BOQ {0} or on this bill").format(self.boq))
		self.validate_measurement_books()
		self.set_item_quantities()
		self.calculate()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_measurement_books(self):
		seen = set()
		for row in self.measurement_books:
			mb = frappe.db.get_value(
				"Measurement Book",
				row.measurement_book,
				["docstatus", "mb_type", "boq", "billing_status", "ra_bill"],
				as_dict=True,
			)
			if row.measurement_book in seen:
				frappe.throw(_("Measurement Book {0} is listed twice").format(row.measurement_book))
			seen.add(row.measurement_book)
			if mb.docstatus != 1 or mb.mb_type != "Client" or mb.boq != self.boq:
				frappe.throw(
					_("Measurement Book {0} is not a submitted client measurement of this BOQ").format(
						row.measurement_book
					)
				)
			if mb.billing_status == "Billed" and mb.ra_bill != self.name:
				frappe.throw(_("Measurement Book {0} is already billed in {1}").format(row.measurement_book, mb.ra_bill))

	def set_item_quantities(self):
		names = [r.measurement_book for r in self.measurement_books]
		measured, excess_ok = {}, set()
		if names:
			for r in frappe.db.sql(
				"""select c.boq_item, sum(c.qty) as qty, max(p.allow_excess) as excess
				from `tabMeasurement Book Item` c join `tabMeasurement Book` p on p.name = c.parent
				where p.name in %s group by c.boq_item""",
				(names,),
				as_dict=True,
			):
				measured[r.boq_item] = flt(r.qty)
				if r.excess:
					excess_ok.add(r.boq_item)
		billed_before = {
			r.boq_item: flt(r.qty)
			for r in frappe.db.sql(
				"""select c.boq_item, sum(c.current_qty) as qty from `tabClient RA Bill Item` c
				join `tabClient RA Bill` p on p.name = c.parent
				where p.docstatus = 1 and p.boq = %s and p.name != %s group by c.boq_item""",
				(self.boq, self.name),
				as_dict=True,
			)
		}
		self.set("items", [])
		for line in frappe.get_all(
			"BOQ Item",
			filters={"parent": self.boq, "parenttype": "BOQ"},
			fields=["name", "boq_ref", "description", "uom", "qty", "rate"],
			order_by="idx",
		):
			current = measured.get(line.name, 0)
			previous = billed_before.get(line.name, 0)
			if not current and not previous:
				continue
			cumulative = previous + current
			if cumulative > flt(line.qty) + 1e-6 and line.name not in excess_ok:
				frappe.throw(
					_("BOQ Ref {0}: billed to date {1} exceeds the BOQ quantity {2}").format(
						frappe.bold(line.boq_ref), cumulative, line.qty
					)
				)
			self.append(
				"items",
				{
					"boq_ref": line.boq_ref,
					"description": line.description,
					"uom": line.uom,
					"rate": line.rate,
					"boq_qty": line.qty,
					"previous_qty": previous,
					"current_qty": current,
					"cumulative_qty": cumulative,
					"current_amount": current * flt(line.rate),
					"boq_item": line.name,
				},
			)

	def calculate(self):
		self.gross_to_date = sum(flt(r.cumulative_qty) * flt(r.rate) for r in self.items)
		self.previous_billed = sum(flt(r.previous_qty) * flt(r.rate) for r in self.items)
		self.current_value = sum(flt(r.current_amount) for r in self.items)
		self.retention_amount = flt(self.current_value * flt(self.retention_percent) / 100, 2)
		recovery_pct = flt(get_settings().client_advance_recovery_percent)
		if self.is_new() and not flt(self.advance_recovery_amount) and recovery_pct:
			self.advance_recovery_amount = flt(self.current_value * recovery_pct / 100, 2)
		self.net_receivable = (
			flt(self.current_value) - flt(self.retention_amount) - flt(self.advance_recovery_amount)
		)

	def before_submit(self):
		if flt(self.current_value) <= 0:
			frappe.throw(_("Nothing to bill: add client measurement books with quantities"))
		self.status = "Submitted"

	def on_submit(self):
		mark_measurements([r.measurement_book for r in self.measurement_books], self.name)
		update_boq_billed(self.boq)

	def before_cancel(self):
		if self.sales_invoice and frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus") == 1:
			frappe.throw(_("Cancel Sales Invoice {0} first").format(frappe.bold(self.sales_invoice)))
		cert = frappe.db.get_value("Certification", {"client_ra_bill": self.name, "docstatus": 1})
		if cert:
			frappe.throw(_("Cancel Certification {0} first").format(frappe.bold(cert)))
		later = frappe.db.get_value(
			"Client RA Bill", {"boq": self.boq, "docstatus": 1, "bill_no": [">", self.bill_no]}
		)
		if later:
			frappe.throw(_("Cancel the later RA bill {0} first").format(frappe.bold(later)))

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		mark_measurements([r.measurement_book for r in self.measurement_books], None)
		update_boq_billed(self.boq)

	@frappe.whitelist()
	def get_measurements(self):
		filters = {"docstatus": 1, "mb_type": "Client", "boq": self.boq, "billing_status": "Not Billed"}
		if self.period_to:
			filters["measurement_date"] = ["<=", getdate(self.period_to)]
		have = {r.measurement_book for r in self.measurement_books}
		for mb in frappe.get_all("Measurement Book", filters=filters, pluck="name", order_by="measurement_date"):
			if mb not in have:
				self.append("measurement_books", {"measurement_book": mb})
		self.validate()
		return self


@frappe.whitelist()
def make_sales_invoice(source_name):
	"""Draft Sales Invoice for the certified (or, if not yet certified, the submitted) value of the bill.

	GST is applied by the taxes template on the invoice; the e-Invoice is generated from it by India Compliance.
	"""
	bill = frappe.get_doc("Client RA Bill", source_name)
	bill.check_permission("read")
	frappe.has_permission("Sales Invoice", "create", throw=True)
	if bill.docstatus != 1:
		frappe.throw(_("Submit the RA bill first"))
	if bill.sales_invoice and frappe.db.get_value("Sales Invoice", bill.sales_invoice, "docstatus") < 2:
		return bill.sales_invoice
	item = require("client_billing_item")
	value = flt(bill.certified_amount) or flt(bill.current_value)
	si = frappe.new_doc("Sales Invoice")
	si.update(
		{
			"customer": bill.customer,
			"company": bill.company,
			"posting_date": bill.bill_date,
			"project": bill.project,
			"remarks": _("RA bill {0} against BOQ {1}").format(bill.bill_no, bill.boq),
		}
	)
	si.append(
		"items",
		{
			"item_code": item,
			"qty": 1,
			"rate": value,
			"project": bill.project,
			"description": _("RA bill {0}: work done up to {1}").format(bill.bill_no, bill.period_to or bill.bill_date),
		},
	)
	si.set_missing_values()
	si.calculate_taxes_and_totals()
	si.insert()
	bill.db_set({"sales_invoice": si.name, "status": "Invoiced"})
	return si.name
