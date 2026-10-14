"""Workflow 7, daily: refresh every active booking's dues and draft demand letters ahead of due dates."""

import frappe
from frappe.utils import add_days, cint, getdate, today

from sanvidhi_epc.utils.collections import refresh_booking
from sanvidhi_epc.utils.settings import get_settings


def daily():
	lead_days = cint(get_settings().demand_lead_days)
	horizon = getdate(add_days(today(), lead_days))
	for name in frappe.get_all("Plot Booking", filters={"docstatus": 1, "status": "Booked"}, pluck="name"):
		try:
			booking = refresh_booking(name)
			for row in booking.payment_schedule:
				if row.demand_letter or row.status == "Paid" or not row.due_date or getdate(row.due_date) > horizon:
					continue
				if frappe.db.exists("Demand Letter", {"schedule_row": row.name, "docstatus": ["<", 2]}):
					continue
				letter = frappe.new_doc("Demand Letter")
				letter.update(
					{
						"company": booking.company,
						"plot_booking": booking.name,
						"milestone": row.milestone,
						"schedule_row": row.name,
						"due_date": row.due_date,
						"letter_date": today(),
					}
				)
				# drafted for the accounts team to check and issue
				letter.insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Demand letters for {name}")
