# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

SYSTEM_STATUSES = ("Booked", "Sold")


class Plot(Document):
	def validate(self):
		if flt(self.area_sqft) <= 0:
			frappe.throw(_("Area must be more than zero"))
		self.base_value = flt(self.area_sqft) * flt(self.rate_per_sqft)
		if self.flags.from_booking:
			return
		before = self.get_doc_before_save()
		old = before.status if before else "Available"
		if self.status != old and (self.status in SYSTEM_STATUSES or old in SYSTEM_STATUSES):
			frappe.throw(
				_("A plot becomes Booked or Sold only through a Plot Booking or Plot Handover; it can be set to Available or Blocked here.")
			)

	def on_trash(self):
		if self.plot_booking:
			frappe.throw(_("Plot {0} has a booking and cannot be deleted").format(self.name))


def set_plot_status(plot, status, customer=None, booking=None):
	doc = frappe.get_doc("Plot", plot)
	doc.status = status
	doc.customer = customer
	doc.plot_booking = booking
	doc.flags.from_booking = True
	doc.flags.ignore_permissions = True
	doc.save()
