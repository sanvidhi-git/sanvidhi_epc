# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from sanvidhi_epc.utils.progress import mark_measurements, update_work_order_billed
from sanvidhi_epc.utils.settings import require


class ContractorRABill(Document):
	def before_insert(self):
		self.bill_no = (
			frappe.db.count(
				"Contractor RA Bill",
				{"contractor_work_order": self.contractor_work_order, "docstatus": ["<", 2]},
			)
			+ 1
		)

	def validate(self):
		self._wo = frappe.get_doc("Contractor Work Order", self.contractor_work_order)
		if self._wo.docstatus != 1:
			frappe.throw(_("Contractor Work Order {0} is not submitted").format(self._wo.name))
		self.project, self.supplier, self.company = self._wo.project, self._wo.supplier, self._wo.company
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
				["docstatus", "mb_type", "contractor_work_order", "billing_status", "ra_bill"],
				as_dict=True,
			)
			if row.measurement_book in seen:
				frappe.throw(_("Measurement Book {0} is listed twice").format(row.measurement_book))
			seen.add(row.measurement_book)
			if mb.docstatus != 1 or mb.mb_type != "Contractor" or mb.contractor_work_order != self._wo.name:
				frappe.throw(
					_("Measurement Book {0} is not a submitted measurement of this work order").format(
						row.measurement_book
					)
				)
			if mb.billing_status == "Billed" and mb.ra_bill != self.name:
				frappe.throw(_("Measurement Book {0} is already billed in {1}").format(row.measurement_book, mb.ra_bill))

	def _measured(self):
		names = [r.measurement_book for r in self.measurement_books]
		if not names:
			return {}, set()
		rows = frappe.db.sql(
			"""select c.work_order_item, sum(c.qty) as qty, max(p.allow_excess) as excess
			from `tabMeasurement Book Item` c join `tabMeasurement Book` p on p.name = c.parent
			where p.name in %s group by c.work_order_item""",
			(names,),
			as_dict=True,
		)
		return {r.work_order_item: flt(r.qty) for r in rows}, {r.work_order_item for r in rows if r.excess}

	def set_item_quantities(self):
		"""Bill lines = work order lines; this-bill qty from the selected measurement books."""
		measured, excess_ok = self._measured()
		billed_before = {
			r.work_order_item: flt(r.qty)
			for r in frappe.db.sql(
				"""select c.work_order_item, sum(c.current_qty) as qty from `tabContractor RA Bill Item` c
				join `tabContractor RA Bill` p on p.name = c.parent
				where p.docstatus = 1 and p.contractor_work_order = %s and p.name != %s
				group by c.work_order_item""",
				(self._wo.name, self.name),
				as_dict=True,
			)
		}
		self.set("items", [])
		for line in self._wo.items:
			current = measured.get(line.name, 0)
			previous = billed_before.get(line.name, 0)
			if not current and not previous:
				continue
			cumulative = previous + current
			if cumulative > flt(line.qty) + 1e-6 and line.name not in excess_ok:
				frappe.throw(
					_("BOQ Ref {0}: billed to date {1} exceeds the order quantity {2}").format(
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
					"order_qty": line.qty,
					"previous_qty": previous,
					"current_qty": current,
					"cumulative_qty": cumulative,
					"current_amount": current * flt(line.rate),
					"work_order_item": line.name,
				},
			)

	def calculate(self):
		self.gross_to_date = sum(flt(r.cumulative_qty) * flt(r.rate) for r in self.items)
		self.previous_billed = sum(flt(r.previous_qty) * flt(r.rate) for r in self.items)
		self.current_value = sum(flt(r.current_amount) for r in self.items)
		self.retention_amount = flt(self.current_value * flt(self.retention_percent) / 100, 2)
		self.tds_amount = flt(self.current_value * flt(self.tds_percent) / 100, 2)

		recovered_elsewhere = flt(
			frappe.db.sql(
				"""select sum(advance_recovery_amount) from `tabContractor RA Bill`
				where docstatus = 1 and contractor_work_order = %s and name != %s""",
				(self._wo.name, self.name),
			)[0][0]
		)
		pending_advance = max(flt(self._wo.mobilisation_advance) - recovered_elsewhere, 0)
		if self.is_new() and not flt(self.advance_recovery_amount):
			self.advance_recovery_amount = min(
				flt(self.current_value * flt(self._wo.advance_recovery_percent) / 100, 2), pending_advance
			)
		if flt(self.advance_recovery_amount) > pending_advance + 0.01:
			frappe.throw(
				_("Advance recovery {0} is more than the advance still to recover {1}").format(
					self.advance_recovery_amount, pending_advance
				)
			)
		self.net_payable = (
			flt(self.current_value)
			- flt(self.retention_amount)
			- flt(self.advance_recovery_amount)
			- flt(self.tds_amount)
			- flt(self.other_deductions)
		)

	def before_submit(self):
		if flt(self.current_value) <= 0:
			frappe.throw(_("Nothing to bill: add measurement books with quantities"))
		self.status = "Certified"

	def on_submit(self):
		mark_measurements([r.measurement_book for r in self.measurement_books], self.name)
		update_work_order_billed(self.contractor_work_order)

	def before_cancel(self):
		for field in ("purchase_invoice", "journal_entry"):
			linked = self.get(field)
			if linked and frappe.db.get_value(self.meta.get_field(field).options, linked, "docstatus") == 1:
				frappe.throw(_("Cancel {0} first").format(frappe.bold(linked)))
		later = frappe.db.get_value(
			"Contractor RA Bill",
			{"contractor_work_order": self.contractor_work_order, "docstatus": 1, "bill_no": [">", self.bill_no]},
		)
		if later:
			frappe.throw(_("Cancel the later RA bill {0} first").format(frappe.bold(later)))

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		mark_measurements([r.measurement_book for r in self.measurement_books], None)
		update_work_order_billed(self.contractor_work_order)

	@frappe.whitelist()
	def get_measurements(self):
		"""Add every submitted, unbilled measurement of this work order up to the 'work up to' date."""
		filters = {
			"docstatus": 1,
			"mb_type": "Contractor",
			"contractor_work_order": self.contractor_work_order,
			"billing_status": "Not Billed",
		}
		if self.period_to:
			filters["measurement_date"] = ["<=", getdate(self.period_to)]
		have = {r.measurement_book for r in self.measurement_books}
		for mb in frappe.get_all("Measurement Book", filters=filters, pluck="name", order_by="measurement_date"):
			if mb not in have:
				self.append("measurement_books", {"measurement_book": mb})
		self.validate()
		return self


@frappe.whitelist()
def make_purchase_invoice(source_name):
	"""Draft Purchase Invoice for the value of this bill. TDS comes from the supplier's withholding category."""
	bill = frappe.get_doc("Contractor RA Bill", source_name)
	bill.check_permission("read")
	frappe.has_permission("Purchase Invoice", "create", throw=True)
	if bill.docstatus != 1:
		frappe.throw(_("Submit the RA bill first"))
	if bill.purchase_invoice and frappe.db.get_value("Purchase Invoice", bill.purchase_invoice, "docstatus") < 2:
		return bill.purchase_invoice
	item = require("contractor_service_item")
	pi = frappe.new_doc("Purchase Invoice")
	pi.update(
		{
			"supplier": bill.supplier,
			"company": bill.company,
			"set_posting_time": 1,
			"posting_date": bill.bill_date,
			"bill_no": f"{bill.name} (RA {bill.bill_no})",
			"bill_date": bill.bill_date,
			"project": bill.project,
			"remarks": _("RA bill {0} against work order {1}").format(bill.name, bill.contractor_work_order),
		}
	)
	pi.append(
		"items",
		{
			"item_code": item,
			"qty": 1,
			"rate": bill.current_value,
			"project": bill.project,
			"description": _("RA bill {0}: work done up to {1}").format(bill.bill_no, bill.period_to or bill.bill_date),
		},
	)
	pi.set_missing_values()
	pi.calculate_taxes_and_totals()
	pi.insert()
	bill.db_set({"purchase_invoice": pi.name, "status": "Invoiced"})
	return pi.name


@frappe.whitelist()
def make_deduction_journal(source_name):
	"""Draft Journal Entry moving retention and advance recovery off the contractor's payable."""
	from erpnext.accounts.party import get_party_account

	bill = frappe.get_doc("Contractor RA Bill", source_name)
	bill.check_permission("read")
	frappe.has_permission("Journal Entry", "create", throw=True)
	if bill.docstatus != 1:
		frappe.throw(_("Submit the RA bill first"))
	amount = flt(bill.retention_amount) + flt(bill.advance_recovery_amount)
	if not amount:
		frappe.throw(_("This bill has no retention or advance recovery"))
	payable = get_party_account("Supplier", bill.supplier, bill.company)
	je = frappe.new_doc("Journal Entry")
	je.update(
		{
			"voucher_type": "Journal Entry",
			"company": bill.company,
			"posting_date": bill.bill_date,
			"user_remark": _("Retention and advance recovery on RA bill {0}").format(bill.name),
		}
	)
	je.append(
		"accounts",
		{
			"account": payable,
			"party_type": "Supplier",
			"party": bill.supplier,
			"debit_in_account_currency": amount,
			"project": bill.project,
		},
	)
	if flt(bill.retention_amount):
		je.append(
			"accounts",
			{
				"account": require("retention_payable_account"),
				"credit_in_account_currency": bill.retention_amount,
				"project": bill.project,
			},
		)
	if flt(bill.advance_recovery_amount):
		advance_account = require("contractor_advance_account")
		row = {
			"account": advance_account,
			"credit_in_account_currency": bill.advance_recovery_amount,
			"project": bill.project,
		}
		if frappe.db.get_value("Account", advance_account, "account_type") in ("Payable", "Receivable"):
			row.update({"party_type": "Supplier", "party": bill.supplier})
		je.append("accounts", row)
	je.insert()
	bill.db_set("journal_entry", je.name)
	return je.name
