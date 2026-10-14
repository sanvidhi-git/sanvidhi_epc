# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, getdate

from sanvidhi_epc.utils.collections import refresh_booking
from sanvidhi_epc.utils.settings import get_settings


class DemandLetter(Document):
	def validate(self):
		booking = frappe.get_doc("Plot Booking", self.plot_booking)
		if booking.docstatus != 1 or booking.status != "Booked":
			frappe.throw(_("Plot Booking {0} is not an active booking").format(self.plot_booking))
		self.company, self.customer, self.plot = booking.company, booking.customer, booking.plot
		row = self.get_schedule_row(booking)
		self.schedule_row, self.milestone = row.name, row.milestone
		self.due_date = self.due_date or row.due_date
		if not flt(self.instalment_amount):
			self.instalment_amount = flt(row.amount) - flt(row.paid_amount)
		duplicate = frappe.db.get_value(
			"Demand Letter",
			{"schedule_row": row.name, "docstatus": ["<", 2], "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(_("Instalment {0} is already demanded in {1}").format(row.milestone, frappe.bold(duplicate)))
		self.set_dues(booking, row)
		if self.docstatus == 0:
			self.status = "Draft"

	def get_schedule_row(self, booking):
		for row in booking.payment_schedule:
			if (self.schedule_row and row.name == self.schedule_row) or (
				not self.schedule_row and row.milestone == self.milestone
			):
				return row
		frappe.throw(_("Milestone {0} is not in the booking's payment schedule").format(frappe.bold(self.milestone)))

	def set_dues(self, booking, this_row):
		"""Unpaid earlier instalments, plus interest on them from their due date to this letter's date."""
		rate = flt(get_settings().late_interest_percent)
		letter_date = getdate(self.letter_date)
		previous, interest = 0, 0
		for row in booking.payment_schedule:
			if row.idx >= this_row.idx:
				break
			unpaid = flt(row.amount) - flt(row.paid_amount)
			if unpaid <= 0:
				continue
			previous += unpaid
			days = date_diff(letter_date, row.due_date) if row.due_date else 0
			if rate and days > 0:
				interest += unpaid * rate / 100 * days / 365
		self.previous_outstanding = previous
		if self.is_new() and not flt(self.late_interest):
			self.late_interest = flt(interest, 2)
		self.total_due = flt(self.instalment_amount) + previous + flt(self.late_interest)

	def before_submit(self):
		self.status = "Issued"

	def on_submit(self):
		frappe.db.set_value("Plot Payment Schedule", self.schedule_row, "demand_letter", self.name)
		refresh_booking(self.plot_booking)
		if get_settings().email_demand_letters:
			self.email_customer()

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		frappe.db.set_value("Plot Payment Schedule", self.schedule_row, "demand_letter", None)
		refresh_booking(self.plot_booking)

	def email_customer(self):
		email = frappe.db.get_value("Customer", self.customer, "email_id")
		if not email:
			frappe.msgprint(_("Customer {0} has no email; print the letter instead").format(self.customer), alert=True)
			return
		frappe.sendmail(
			recipients=[email],
			subject=_("Demand for {0} - Plot {1}").format(self.milestone, self.plot),
			message=_("Dear {0},<br><br>Please find attached the demand letter for {1}, due by {2}.").format(
				self.customer_name, self.milestone, frappe.format(self.due_date, {"fieldtype": "Date"})
			),
			attachments=[frappe.attach_print(self.doctype, self.name, print_format="Demand Letter")],
			reference_doctype=self.doctype,
			reference_name=self.name,
		)
		self.db_set("email_sent", 1)
