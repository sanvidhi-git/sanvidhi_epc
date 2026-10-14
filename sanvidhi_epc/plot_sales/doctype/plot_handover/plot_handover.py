# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sanvidhi_epc.plot_sales.doctype.plot.plot import set_plot_status
from sanvidhi_epc.utils.collections import refresh_booking

STANDARD_DOCUMENTS = [
	("Registered sale deed", 1),
	("Index II", 1),
	("No-dues certificate", 1),
	("7/12 mutation entry", 0),
	("Buyer ID and address proof", 1),
	("Possession letter acknowledgement", 1),
]


class PlotHandover(Document):
	def onload(self):
		if self.is_new() and not self.documents:
			self.set_standard_documents()

	def set_standard_documents(self):
		for document, mandatory in STANDARD_DOCUMENTS:
			self.append("documents", {"document": _(document), "mandatory": mandatory})

	def validate(self):
		booking = frappe.db.get_value(
			"Plot Booking", self.plot_booking, ["docstatus", "status", "plot", "customer", "agreed_value"], as_dict=True
		)
		if booking.docstatus != 1 or booking.status not in ("Booked", "Sold"):
			frappe.throw(_("Plot Booking {0} is not an active booking").format(self.plot_booking))
		self.plot, self.customer, self.agreed_value = booking.plot, booking.customer, booking.agreed_value
		other = frappe.db.get_value(
			"Plot Handover", {"plot_booking": self.plot_booking, "docstatus": 1, "name": ["!=", self.name]}
		)
		if other:
			frappe.throw(_("Plot already handed over in {0}").format(frappe.bold(other)))
		if not self.documents:
			self.set_standard_documents()
		self.set_dues()

	def set_dues(self):
		booking = refresh_booking(self.plot_booking)
		self.total_paid = flt(booking.total_paid)
		self.dues_outstanding = flt(self.agreed_value) - self.total_paid

	def before_submit(self):
		if self.dues_outstanding > 0.5:
			frappe.throw(
				_("Dues of {0} are outstanding. The possession letter is issued only when dues are nil.").format(
					frappe.format(self.dues_outstanding, {"fieldtype": "Currency"})
				),
				title=_("Dues outstanding"),
			)
		missing = [d.document for d in self.documents if d.mandatory and not d.received]
		if missing:
			frappe.throw(_("Documents not yet received: {0}").format(", ".join(missing)))
		if not (self.registration_date and self.registration_no):
			frappe.throw(_("Enter the registration date and registered document number"))
		self.no_dues_confirmed_by = frappe.session.user

	def on_submit(self):
		booking = frappe.get_doc("Plot Booking", self.plot_booking)
		set_plot_status(self.plot, "Sold", booking.customer, booking.name)
		booking.db_set("status", "Sold")

	def on_cancel(self):
		booking = frappe.get_doc("Plot Booking", self.plot_booking)
		set_plot_status(self.plot, "Booked", booking.customer, booking.name)
		booking.db_set("status", "Booked")
