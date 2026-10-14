"""End-to-end scenario for Sanvidhi EPC: every workflow, including the negative cases.

Creates its own tagged test data (items, accounts, project, BOQ, work order, measurements, bills,
plots, bookings) and checks each control.

    bench --site <test-site> execute sanvidhi_epc.tests.scenario_workflows.run

Needs a company (setup wizard done). Run it on a test site only - it posts invoices and journal entries.
"""

import time
import traceback

import frappe
from frappe.utils import add_days, flt, today


def run():
	frappe.set_user("Administrator")
	TAG = str(int(time.time()))[-6:]
	RESULTS = []
	COMPANY = frappe.db.get_value("Company", {}, "name")
	ABBR = frappe.db.get_value("Company", COMPANY, "abbr")
	CRA = "sanvidhi_epc.epc_projects.doctype.contractor_ra_bill.contractor_ra_bill"

	def check(name, fn):
		try:
			out = fn()
			RESULTS.append(("PASS", name, out if out is not None else ""))
			frappe.db.commit()
			return out
		except Exception as e:
			frappe.db.rollback()
			RESULTS.append(("FAIL", name, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"))
			return None

	def expect_error(name, fn, contains=None):
		try:
			fn()
		except Exception as e:
			frappe.db.rollback()
			msg = str(e)
			if contains and contains.lower() not in msg.lower():
				RESULTS.append(("FAIL", name, f"wrong error: {msg}"))
			else:
				RESULTS.append(("PASS", name, f"blocked: {msg[:120]}"))
			frappe.clear_messages()
			return
		frappe.db.rollback()
		RESULTS.append(("FAIL", name, "no error raised"))

	def assert_eq(a, b, what):
		if abs(flt(a) - flt(b)) > 0.01 if isinstance(b, (int, float)) else a != b:
			raise AssertionError(f"{what}: expected {b}, got {a}")

	# ------------------------------------------------------------ masters
	def masters():
		for code in ("EPC Contract Service", "EPC Client Billing", "EPC Plot Sale"):
			if not frappe.db.exists("Item", code):
				frappe.get_doc(
					{"doctype": "Item", "item_code": code, "item_group": "Services", "stock_uom": "Nos",
					 "is_stock_item": 0, "include_item_in_manufacturing": 0}
				).insert()
		parent_liab = frappe.db.get_value(
			"Account", {"company": COMPANY, "is_group": 1, "root_type": "Liability", "account_type": ""}, "name",
			order_by="lft desc")
		parent_asset = frappe.db.get_value(
			"Account", {"company": COMPANY, "is_group": 1, "root_type": "Asset", "account_type": ""}, "name",
			order_by="lft desc")
		for name, parent in (("EPC Retention Payable", parent_liab), ("EPC Contractor Advances", parent_asset),
				("EPC Retention Receivable", parent_asset)):
			if not frappe.db.exists("Account", f"{name} - {ABBR}"):
				frappe.get_doc({"doctype": "Account", "account_name": name, "parent_account": parent,
					"company": COMPANY, "is_group": 0}).insert()
		s = frappe.get_single("Sanvidhi EPC Settings")
		s.update({
			"company": COMPANY, "contractor_service_item": "EPC Contract Service",
			"client_billing_item": "EPC Client Billing", "plot_sale_item": "EPC Plot Sale",
			"retention_payable_account": f"EPC Retention Payable - {ABBR}",
			"contractor_advance_account": f"EPC Contractor Advances - {ABBR}",
			"retention_receivable_account": f"EPC Retention Receivable - {ABBR}",
			"default_retention_percent": 5, "default_tds_percent": 2, "default_advance_recovery_percent": 10,
			"client_retention_percent": 5, "max_discount_percent": 2, "email_demand_letters": 0,
			"digest_enabled": 0, "enforce_dpr_before_material_request": 0, "late_interest_percent": 12,
		})
		s.save()
		cust = frappe.get_doc({"doctype": "Customer", "customer_name": f"EPC Client {TAG}", "customer_type": "Company"}).insert()
		buyer = frappe.get_doc({"doctype": "Customer", "customer_name": f"Plot Buyer {TAG}", "customer_type": "Individual"}).insert()
		sup = frappe.get_doc({"doctype": "Supplier", "supplier_name": f"Road Contractor {TAG}", "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()
		proj = frappe.get_doc({"doctype": "Project", "project_name": f"Khopoli Roads {TAG}", "company": COMPANY, "customer": cust.name}).insert()
		layout = frappe.get_doc({"doctype": "Project", "project_name": f"Sun Valley Layout {TAG}", "company": COMPANY}).insert()
		return {"customer": cust.name, "buyer": buyer.name, "supplier": sup.name, "project": proj.name, "layout": layout.name}

	M = check("Masters and settings", masters)
	if not M:
		return report(RESULTS)

	# ------------------------------------------------------------ W1 BOQ
	def make_boq():
		boq = frappe.get_doc({
			"doctype": "BOQ", "boq_title": f"Internal roads {TAG}", "company": COMPANY, "project": M["project"],
			"items": [
				{"boq_ref": "1.1", "description": "Earthwork excavation", "uom": "Nos", "qty": 1200, "rate": 180, "cost_head": "Subcontract", "cost_rate": 140},
				{"boq_ref": "1.2", "description": "PCC M10 bed", "uom": "Nos", "qty": 85, "rate": 5200, "cost_head": "Material", "cost_rate": 4300},
				{"boq_ref": "2.1", "description": "Internal road WBM", "uom": "Nos", "qty": 3400, "rate": 420, "cost_head": "Subcontract", "cost_rate": 330},
			],
		}).insert()
		boq.submit()
		assert_eq(boq.total_contract_value, 1200 * 180 + 85 * 5200 + 3400 * 420, "contract value")
		assert_eq(boq.status, "Active", "BOQ status")
		assert_eq(frappe.db.get_value("Project", M["project"], "estimated_costing"), boq.total_budgeted_cost, "project estimate")
		assert_eq(boq.customer, M["customer"], "client from project")
		return boq.name

	BOQ = check("W1 BOQ submitted; budget written to project", make_boq)

	def second_boq():
		frappe.get_doc({"doctype": "BOQ", "boq_title": "dup", "company": COMPANY, "project": M["project"],
			"items": [{"boq_ref": "1", "description": "x", "uom": "Nos", "qty": 1, "rate": 1}]}).insert().submit()

	expect_error("W1 Second active BOQ on the same project is refused", second_boq, "already has an active BOQ")

	# ------------------------------------------------------------ W2 work order
	def make_wo():
		wo = frappe.get_doc({
			"doctype": "Contractor Work Order", "company": COMPANY, "project": M["project"], "boq": BOQ,
			"supplier": M["supplier"], "mobilisation_advance": 50000, "advance_recovery_percent": 10,
			"items": [
				{"boq_ref": "1.1", "qty": 1200, "rate": 140},
				{"boq_ref": "2.1", "qty": 1000, "rate": 330},
			],
		}).insert()
		assert_eq(wo.retention_percent, 5, "default retention")
		assert_eq(wo.tds_percent, 2, "default TDS")
		wo.submit()
		contracted = frappe.db.get_value("BOQ Item", {"parent": BOQ, "boq_ref": "2.1"}, "contracted_qty")
		assert_eq(contracted, 1000, "BOQ awarded qty")
		return wo.name

	WO = check("W2 Contractor work order from BOQ; BOQ shows awarded qty", make_wo)

	# ------------------------------------------------------------ W3 measurement
	def mb(qty, ref="2.1", mb_type="Contractor", **kw):
		doc = frappe.get_doc({
			"doctype": "Measurement Book", "company": COMPANY, "project": M["project"], "boq": BOQ,
			"mb_type": mb_type, "contractor_work_order": WO if mb_type == "Contractor" else None,
			"items": [{"boq_ref": ref, "nos": 1, "qty": qty}], **kw,
		}).insert()
		doc.submit()
		return doc

	MB1 = check("W3 Contractor measurement 600 submitted", lambda: mb(600).name)
	check("W3 Work order measured qty rolled up", lambda: assert_eq(
		frappe.db.get_value("Contractor Work Order Item", {"parent": WO, "boq_ref": "2.1"}, "measured_qty"), 600, "measured"))
	expect_error("W3 Measuring beyond the order quantity is refused", lambda: mb(500), "exceed")

	def dims():
		doc = frappe.get_doc({"doctype": "Measurement Book", "company": COMPANY, "project": M["project"], "boq": BOQ,
			"mb_type": "Contractor", "contractor_work_order": WO,
			"items": [{"boq_ref": "1.1", "nos": 2, "length": 10, "breadth": 5, "depth": 1.5}]}).insert()
		assert_eq(doc.items[0].qty, 150, "Nos x L x B x D")
		frappe.delete_doc("Measurement Book", doc.name)

	check("W3 Quantity from Nos x L x B x D", dims)

	# ------------------------------------------------------------ W4 contractor RA bill
	def ra_bill():
		bill = frappe.new_doc("Contractor RA Bill")
		bill.update({"company": COMPANY, "contractor_work_order": WO})
		bill.get_measurements()
		bill.insert()
		assert_eq(bill.bill_no, 1, "bill no")
		assert_eq(bill.current_value, 600 * 330, "this bill")
		assert_eq(bill.retention_amount, 600 * 330 * 0.05, "retention")
		assert_eq(bill.advance_recovery_amount, min(600 * 330 * 0.10, 50000), "advance recovery")
		assert_eq(bill.tds_amount, 600 * 330 * 0.02, "tds")
		assert_eq(bill.net_payable, 198000 - 9900 - 19800 - 3960, "net payable")
		bill.submit()
		assert_eq(frappe.db.get_value("Measurement Book", MB1, "billing_status"), "Billed", "MB billed")
		assert_eq(frappe.db.get_value("Contractor Work Order", WO, "billed_amount"), 198000, "WO billed")
		return bill.name

	RA = check("W4 Contractor RA bill: retention, advance recovery, TDS, net", ra_bill)
	expect_error("W4 A billed measurement cannot be cancelled",
		lambda: frappe.get_doc("Measurement Book", MB1).cancel(), "Cancel RA bill")

	def ra_docs():
		pi = frappe.get_doc("Purchase Invoice", frappe.call(f"{CRA}.make_purchase_invoice", source_name=RA))
		assert_eq(pi.items[0].rate, 198000, "PI rate")
		assert_eq(pi.project, M["project"], "PI project")
		je = frappe.get_doc("Journal Entry", frappe.call(f"{CRA}.make_deduction_journal", source_name=RA))
		assert_eq(je.total_debit, 9900 + 19800, "JE debit")
		assert_eq(frappe.db.get_value("Contractor RA Bill", RA, "status"), "Invoiced", "RA status")
		return f"{pi.name}, {je.name}"

	check("W4 Draft Purchase Invoice and retention/advance journal made", ra_docs)

	# ------------------------------------------------------------ W5/W6 client billing + certification
	def client_bill():
		mb(800, ref="2.1", mb_type="Client")
		bill = frappe.new_doc("Client RA Bill")
		bill.update({"company": COMPANY, "boq": BOQ})
		bill.get_measurements()
		bill.insert()
		assert_eq(bill.current_value, 800 * 420, "client bill value")
		assert_eq(bill.retention_amount, 800 * 420 * 0.05, "client retention")
		bill.submit()
		assert_eq(frappe.db.get_value("BOQ Item", {"parent": BOQ, "boq_ref": "2.1"}, "billed_qty"), 800, "BOQ billed qty")
		return bill.name

	CB = check("W5 Client RA bill from client measurement", client_bill)
	expect_error("W5 Client measurement beyond BOQ quantity is refused", lambda: mb(3000, ref="2.1", mb_type="Client"), "exceed")

	def cert(reason):
		return frappe.get_doc({"doctype": "Certification", "client_ra_bill": CB, "certified_by": "Client engineer",
			"certified_amount": 320000, "reason_for_difference": reason}).insert()

	expect_error("W6 Short certification without a reason is refused", lambda: cert(None), "reason")

	def certify():
		c = cert("Two chainages not accepted")
		c.submit()
		bill = frappe.get_doc("Client RA Bill", CB)
		assert_eq(bill.status, "Certified", "client bill status")
		assert_eq(bill.certified_amount, 320000, "certified amount")
		si = frappe.get_doc("Sales Invoice", frappe.call(
			"sanvidhi_epc.epc_projects.doctype.client_ra_bill.client_ra_bill.make_sales_invoice", source_name=CB))
		assert_eq(si.items[0].rate, 320000, "invoice at certified value")
		return si.name

	check("W6 Certification sets certified value; invoice raised for it", certify)

	# ------------------------------------------------------------ W8 DPR + digest
	def dpr(day=None):
		d = frappe.get_doc({"doctype": "Daily Progress Report", "company": COMPANY, "project": M["project"],
			"report_date": day or today(), "work_done": [{"boq_ref": "2.1", "description": "WBM layer 1", "uom": "Nos", "qty_done": 120}],
			"labour": [{"category": "Helper", "count": 12}, {"category": "Operator", "count": 2}]}).insert()
		d.submit()
		return d

	check("W8 DPR submitted; headcount totalled", lambda: assert_eq(dpr().total_labour, 14, "headcount"))
	expect_error("W8 Second DPR for the same day is refused", lambda: dpr(), "already has a progress report")

	def digest():
		from sanvidhi_epc.tasks.digest import build_digest

		d = build_digest(today())
		row = [s for s in d.sites if s.project == M["project"]][0]
		assert_eq(row.status, "Reported", "digest row")
		return d.name

	check("W8 Daily digest lists the site as reported", digest)

	def mr_rule():
		frappe.db.set_single_value("Sanvidhi EPC Settings", "enforce_dpr_before_material_request", 1)
		frappe.clear_document_cache("Sanvidhi EPC Settings", "Sanvidhi EPC Settings")
		try:
			frappe.get_doc({"doctype": "Material Request", "material_request_type": "Purchase", "company": COMPANY,
				"transaction_date": today(), "schedule_date": today(),
				"items": [{"item_code": "EPC Contract Service", "qty": 1, "schedule_date": today(), "project": M["project"],
					"uom": "Nos", "conversion_factor": 1}]}).insert()
		finally:
			frappe.db.set_single_value("Sanvidhi EPC Settings", "enforce_dpr_before_material_request", 0)
			frappe.clear_document_cache("Sanvidhi EPC Settings", "Sanvidhi EPC Settings")

	expect_error("W8 Material request held until yesterday's DPR is in (rule on)", mr_rule, "Daily Progress Report")

	# ------------------------------------------------------------ W6/W7 plots
	def plot(no):
		return frappe.get_doc({"doctype": "Plot", "layout": M["layout"], "plot_no": no, "area_sqft": 3500,
			"rate_per_sqft": 480, "plot_type": "Residential"}).insert().name

	P1 = check("Plot master created", lambda: plot(f"P-{TAG}-1"))

	def booking(discount=0, schedule=None, user=None, submit=True):
		agreed = 3500 * 480 * (1 - discount / 100)
		rows = schedule or [
			{"milestone": "Booking", "due_date": today(), "amount": agreed * 0.10},
			{"milestone": "Agreement", "due_date": add_days(today(), 30), "amount": agreed * 0.40},
			{"milestone": "Registration", "due_date": add_days(today(), 120), "amount": agreed * 0.50},
		]
		b = frappe.get_doc({"doctype": "Plot Booking", "company": COMPANY, "plot": P1, "customer": M["buyer"],
			"discount_percent": discount, "payment_schedule": rows}).insert()
		if submit:
			b.submit()
		return b

	expect_error("W7 Schedule not adding up to the agreed value is refused",
		lambda: booking(schedule=[{"milestone": "Booking", "due_date": today(), "amount": 1000}]), "must equal")

	def sales_user_discount():
		email = f"plotsales{TAG}@example.com"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Plot Sales", "send_welcome_email": 0})
			u.append("roles", {"role": "Plot Sales User"})
			u.insert(ignore_permissions=True)
		b = booking(discount=5, submit=False)
		frappe.db.commit()
		frappe.set_user(email)
		try:
			frappe.get_doc("Plot Booking", b.name).submit()
		finally:
			frappe.set_user("Administrator")

	expect_error("W7 Discount above the limit needs the EPC MD", sales_user_discount, "MD")
	for name in frappe.get_all("Plot Booking", filters={"plot": P1, "docstatus": 0}, pluck="name"):
		frappe.delete_doc("Plot Booking", name, force=True)
	frappe.db.commit()

	B = check("W7 Plot booked; plot status Booked", lambda: (
		lambda b: (assert_eq(frappe.db.get_value("Plot", P1, "status"), "Booked", "plot status"), b.name)[1])(booking()))
	expect_error("W7 Same plot cannot be booked twice", lambda: booking(), "")

	def so_and_receipt():
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		so = frappe.get_doc("Sales Order", frappe.call(
			"sanvidhi_epc.plot_sales.doctype.plot_booking.plot_booking.make_sales_order", source_name=B))
		so.submit()
		pe = get_payment_entry("Sales Order", so.name)
		pe.paid_amount = pe.received_amount = 168000
		pe.references[0].allocated_amount = 168000
		pe.reference_no, pe.reference_date = f"UTR{TAG}", today()
		pe.insert()
		pe.submit()
		b = frappe.get_doc("Plot Booking", B)
		assert_eq(b.total_paid, 168000, "received")
		assert_eq(b.payment_schedule[0].status, "Paid", "first instalment paid")
		return so.name

	SO = check("W7 Sales order with schedule; receipt refreshes the booking", so_and_receipt)

	def demand():
		d = frappe.get_doc({"doctype": "Demand Letter", "company": COMPANY, "plot_booking": B, "milestone": "Agreement",
			"due_date": add_days(today(), 30)}).insert()
		assert_eq(d.total_due, 3500 * 480 * 0.40, "demand total")
		d.submit()
		row = frappe.get_doc("Plot Booking", B).payment_schedule[1]
		assert_eq(row.demand_letter, d.name, "schedule row linked")
		return d.name

	check("W7 Demand letter issued for the next instalment", demand)
	check("W7 Daily job runs (dues refresh, letters drafted)", lambda: frappe.get_attr("sanvidhi_epc.tasks.demand.daily")())

	def handover(submit=True):
		h = frappe.new_doc("Plot Handover")
		h.update({"company": COMPANY, "plot_booking": B, "registration_no": f"REG/{TAG}", "registration_date": today()})
		h.insert()
		for d in h.documents:
			d.received = 1
		h.save()
		if submit:
			h.submit()
		return h

	expect_error("W7 Possession refused while dues are outstanding", handover, "outstanding")

	def pay_rest_and_handover():
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		pe = get_payment_entry("Sales Order", SO)
		pe.reference_no, pe.reference_date = f"UTR2{TAG}", today()
		pe.insert()
		pe.submit()
		for name in frappe.get_all("Plot Handover", filters={"plot_booking": B, "docstatus": 0}, pluck="name"):
			frappe.delete_doc("Plot Handover", name, force=True)
		h = handover()
		assert_eq(frappe.db.get_value("Plot", P1, "status"), "Sold", "plot sold")
		assert_eq(frappe.db.get_value("Plot Booking", B, "status"), "Sold", "booking sold")
		return h.name

	check("W7 Possession after full payment; plot Sold", pay_rest_and_handover)

	return report(RESULTS)


def report(results):
	passed = sum(1 for r in results if r[0] == "PASS")
	lines = [f"{s}  {n}" + (f"\n      {d}" if s == "FAIL" else "") for s, n, d in results]
	print("\n".join(lines))
	print(f"\n{passed}/{len(results)} checks passed")
	return {"passed": passed, "total": len(results)}
