"""Roll-ups from measurement and billing back to the work order and the BOQ.

Every figure is recomputed from the submitted documents rather than incremented, so a
cancel or an amendment always leaves the parent right.
"""

import frappe
from frappe.utils import flt


def _sum_by(child, parent, key, value, filters):
	conditions = " and ".join(f"p.`{k}` = %({k})s" for k in filters)
	rows = frappe.db.sql(
		f"""select c.`{key}` as k, sum(c.`{value}`) as v
		from `tab{child}` c join `tab{parent}` p on p.name = c.parent
		where p.docstatus = 1 and {conditions} and ifnull(c.`{key}`, '') != ''
		group by c.`{key}`""",
		filters,
		as_dict=True,
	)
	return {r.k: flt(r.v) for r in rows}


def update_boq_contracted(boq):
	qty = _sum_by("Contractor Work Order Item", "Contractor Work Order", "boq_item", "qty", {"boq": boq})
	for row in frappe.get_all("BOQ Item", filters={"parent": boq, "parenttype": "BOQ"}, pluck="name"):
		frappe.db.set_value("BOQ Item", row, "contracted_qty", qty.get(row, 0), update_modified=False)


def update_boq_executed(boq):
	qty = _sum_by("Measurement Book Item", "Measurement Book", "boq_item", "qty", {"boq": boq, "mb_type": "Client"})
	for row in frappe.get_all("BOQ Item", filters={"parent": boq, "parenttype": "BOQ"}, pluck="name"):
		frappe.db.set_value("BOQ Item", row, "executed_qty", qty.get(row, 0), update_modified=False)


def update_boq_billed(boq):
	qty = _sum_by("Client RA Bill Item", "Client RA Bill", "boq_item", "current_qty", {"boq": boq})
	for row in frappe.get_all("BOQ Item", filters={"parent": boq, "parenttype": "BOQ"}, pluck="name"):
		frappe.db.set_value("BOQ Item", row, "billed_qty", qty.get(row, 0), update_modified=False)


def update_work_order_measured(work_order):
	qty = _sum_by(
		"Measurement Book Item",
		"Measurement Book",
		"work_order_item",
		"qty",
		{"contractor_work_order": work_order, "mb_type": "Contractor"},
	)
	total = 0
	for row in frappe.get_all(
		"Contractor Work Order Item", filters={"parent": work_order}, fields=["name", "rate"]
	):
		measured = qty.get(row.name, 0)
		total += measured * flt(row.rate)
		frappe.db.set_value("Contractor Work Order Item", row.name, "measured_qty", measured, update_modified=False)
	frappe.db.set_value("Contractor Work Order", work_order, "measured_amount", total, update_modified=False)


def update_work_order_billed(work_order):
	qty = _sum_by(
		"Contractor RA Bill Item",
		"Contractor RA Bill",
		"work_order_item",
		"current_qty",
		{"contractor_work_order": work_order},
	)
	for row in frappe.get_all("Contractor Work Order Item", filters={"parent": work_order}, pluck="name"):
		frappe.db.set_value("Contractor Work Order Item", row, "billed_qty", qty.get(row, 0), update_modified=False)

	totals = frappe.db.sql(
		"""select sum(current_value), sum(advance_recovery_amount) from `tabContractor RA Bill`
		where docstatus = 1 and contractor_work_order = %s""",
		work_order,
	)[0]
	billed, recovered = flt(totals[0]), flt(totals[1])
	wo = frappe.db.get_value("Contractor Work Order", work_order, ["total_amount", "status"], as_dict=True)
	values = {"billed_amount": billed, "advance_recovered": recovered}
	if wo.status in ("Open", "Completed"):
		values["status"] = "Completed" if billed >= flt(wo.total_amount) - 0.5 else "Open"
	frappe.db.set_value("Contractor Work Order", work_order, values, update_modified=False)


def mark_measurements(measurement_books, ra_bill=None):
	"""Flag the measurement books a bill consumed (or release them when it is cancelled)."""
	for mb in measurement_books:
		frappe.db.set_value(
			"Measurement Book",
			mb,
			{"billing_status": "Billed" if ra_bill else "Not Billed", "ra_bill": ra_bill or ""},
			update_modified=False,
		)
