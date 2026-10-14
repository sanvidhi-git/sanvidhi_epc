"""Plot collections: what a buyer has paid against a booking's sales order, spread over its schedule."""

import frappe
from frappe.utils import flt, getdate, today


def received_against_sales_order(sales_order):
	"""Advances received against the order plus whatever has been paid on invoices made from it."""
	if not sales_order:
		return 0
	advances = frappe.db.sql(
		"""select sum(r.allocated_amount) from `tabPayment Entry Reference` r
		join `tabPayment Entry` p on p.name = r.parent
		where p.docstatus = 1 and r.reference_doctype = 'Sales Order' and r.reference_name = %s""",
		sales_order,
	)[0][0]
	invoiced_paid = frappe.db.sql(
		"""select sum(si.grand_total - si.outstanding_amount) from `tabSales Invoice` si
		where si.docstatus = 1 and si.name in (
			select distinct parent from `tabSales Invoice Item` where sales_order = %s)""",
		sales_order,
	)[0][0]
	return flt(advances) + flt(invoiced_paid)


def refresh_booking(booking_name):
	"""Recompute received / outstanding on a submitted booking and each instalment's status (FIFO)."""
	booking = frappe.get_doc("Plot Booking", booking_name)
	if booking.docstatus != 1:
		return booking
	paid = received_against_sales_order(booking.sales_order)
	remaining = paid
	now = getdate(today())
	for row in booking.payment_schedule:
		row.paid_amount = min(flt(row.amount), max(remaining, 0))
		remaining -= row.paid_amount
		if row.paid_amount >= flt(row.amount) - 0.5:
			row.status = "Paid"
		elif row.paid_amount > 0:
			row.status = "Partly Paid"
		elif row.due_date and getdate(row.due_date) < now:
			row.status = "Overdue"
		elif row.demand_letter:
			row.status = "Demanded"
		else:
			row.status = "Not Due"
		row.db_update()
	booking.db_set(
		{"total_paid": paid, "outstanding": flt(booking.agreed_value) - paid}, update_modified=False
	)
	return booking


def _bookings_for_orders(orders):
	orders = {o for o in orders if o}
	if not orders:
		return []
	return frappe.get_all(
		"Plot Booking", filters={"sales_order": ["in", list(orders)], "docstatus": 1}, pluck="name"
	)


def on_payment_entry(doc, method=None):
	orders = {r.reference_name for r in doc.references if r.reference_doctype == "Sales Order"}
	invoices = [r.reference_name for r in doc.references if r.reference_doctype == "Sales Invoice"]
	if invoices:
		orders |= set(
			frappe.get_all(
				"Sales Invoice Item", filters={"parent": ["in", invoices]}, pluck="sales_order", distinct=True
			)
		)
	for booking in _bookings_for_orders(orders):
		refresh_booking(booking)


def on_sales_invoice(doc, method=None):
	for booking in _bookings_for_orders({row.sales_order for row in doc.items}):
		refresh_booking(booking)
