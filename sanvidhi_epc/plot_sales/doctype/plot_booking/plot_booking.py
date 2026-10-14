# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from sanvidhi_epc.plot_sales.doctype.plot.plot import set_plot_status
from sanvidhi_epc.utils.collections import refresh_booking
from sanvidhi_epc.utils.permissions import MD_ROLES, user_has_any
from sanvidhi_epc.utils.settings import get_settings, require


class PlotBooking(Document):
	def validate(self):
		self.validate_plot()
		self.set_price()
		self.validate_schedule()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_plot(self):
		plot = frappe.db.get_value("Plot", self.plot, ["status", "plot_booking", "area_sqft", "layout"], as_dict=True)
		if plot.status != "Available" and plot.plot_booking != self.name:
			frappe.throw(_("Plot {0} is {1}").format(frappe.bold(self.plot), _(plot.status)), title=_("Plot not available"))
		other = frappe.db.get_value(
			"Plot Booking", {"plot": self.plot, "docstatus": 1, "name": ["!=", self.name]}
		)
		if other:
			frappe.throw(_("Plot {0} is already booked in {1}").format(self.plot, frappe.bold(other)))
		self.area_sqft, self.layout = plot.area_sqft, plot.layout

	def set_price(self):
		self.base_value = flt(self.area_sqft) * flt(self.rate_per_sqft)
		if not 0 <= flt(self.discount_percent) <= 100:
			frappe.throw(_("Discount % must be between 0 and 100"))
		self.discount_amount = flt(self.base_value * flt(self.discount_percent) / 100, 2)
		self.agreed_value = flt(self.base_value - self.discount_amount, 2)
		self.broker_commission = flt(self.agreed_value * flt(self.broker_commission_percent) / 100, 2)
		if flt(self.token_amount) > self.agreed_value:
			frappe.throw(_("Token amount cannot be more than the agreed value"))

	def validate_schedule(self):
		last = None
		for row in self.payment_schedule:
			if flt(row.percent) and not flt(row.amount):
				row.amount = flt(self.agreed_value * flt(row.percent) / 100, 2)
			elif flt(row.amount) and self.agreed_value:
				row.percent = flt(row.amount) / self.agreed_value * 100
			if row.due_date and last and getdate(row.due_date) < last:
				frappe.throw(_("Row {0}: instalments must be in due-date order").format(row.idx))
			if row.due_date:
				last = getdate(row.due_date)
		self.total_scheduled = sum(flt(r.amount) for r in self.payment_schedule)
		if abs(self.total_scheduled - flt(self.agreed_value)) > 1:
			frappe.throw(
				_("Payment schedule adds up to {0}; it must equal the agreed value {1}").format(
					frappe.format(self.total_scheduled, {"fieldtype": "Currency"}),
					frappe.format(self.agreed_value, {"fieldtype": "Currency"}),
				)
			)
		if any(not r.due_date for r in self.payment_schedule):
			frappe.throw(_("Every instalment needs a due date"))

	def before_submit(self):
		limit = flt(get_settings().max_discount_percent)
		if flt(self.discount_percent) > limit:
			if not user_has_any(MD_ROLES):
				frappe.throw(
					_("A discount above {0}% needs the EPC MD to submit this booking").format(limit),
					title=_("MD approval needed"),
				)
			self.discount_approved_by = frappe.session.user
		self.status = "Booked"

	def on_submit(self):
		set_plot_status(self.plot, "Booked", self.customer, self.name)

	def before_cancel(self):
		handover = frappe.db.get_value("Plot Handover", {"plot_booking": self.name, "docstatus": 1})
		if handover:
			frappe.throw(_("Cancel Plot Handover {0} first").format(frappe.bold(handover)))
		if self.sales_order and frappe.db.get_value("Sales Order", self.sales_order, "docstatus") == 1:
			frappe.throw(_("Cancel Sales Order {0} first").format(frappe.bold(self.sales_order)))

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		set_plot_status(self.plot, "Available")

	@frappe.whitelist()
	def refresh_collections(self):
		return refresh_booking(self.name)


@frappe.whitelist()
def make_sales_order(source_name):
	"""Draft Sales Order for the agreed value, carrying the instalments as its payment schedule."""
	booking = frappe.get_doc("Plot Booking", source_name)
	booking.check_permission("read")
	frappe.has_permission("Sales Order", "create", throw=True)
	if booking.docstatus != 1:
		frappe.throw(_("Submit the booking first"))
	if booking.sales_order and frappe.db.get_value("Sales Order", booking.sales_order, "docstatus") < 2:
		return booking.sales_order
	so = frappe.new_doc("Sales Order")
	so.update(
		{
			"customer": booking.customer,
			"company": booking.company,
			"transaction_date": booking.booking_date,
			"delivery_date": max(getdate(r.due_date) for r in booking.payment_schedule),
			"project": booking.layout,
		}
	)
	so.append(
		"items",
		{
			"item_code": require("plot_sale_item"),
			"qty": 1,
			"rate": booking.agreed_value,
			"description": _("Plot {0}, {1} sq ft, layout {2}").format(
				frappe.db.get_value("Plot", booking.plot, "plot_no"), booking.area_sqft, booking.layout
			),
		}
	)
	for row in booking.payment_schedule:
		so.append(
			"payment_schedule",
			{
				"due_date": row.due_date,
				"invoice_portion": flt(row.amount) / flt(booking.agreed_value) * 100,
				"payment_amount": row.amount,
				"description": row.milestone,
			},
		)
	so.set_missing_values()
	so.calculate_taxes_and_totals()
	so.insert()
	booking.db_set("sales_order", so.name)
	return so.name
