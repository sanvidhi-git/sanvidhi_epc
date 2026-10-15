"""Demo data for the Sanvidhi EPC MD demo (Srushti Infra & Agro storyline).

Builds, step by step, everything the 60-minute run sheet shows: an EPC site (Khopoli internal roads)
from BOQ to client invoice, site stores, subcontractors, daily reports, and a plotted layout
(Sun Valley Farm) with plots open, booked and sold.

Run every step in order (each step runs once; re-running skips steps already done):

    bench --site <demo-site> execute sanvidhi_epc.demo.demo_data.run

Run, or re-run, a single step:

    bench --site <demo-site> execute sanvidhi_epc.demo.demo_data.run --kwargs "{'step': 7}"

List the steps and which are done:

    bench --site <demo-site> execute sanvidhi_epc.demo.demo_data.status

Needs: ERPNext set up with one company (setup wizard done), Sanvidhi EPC installed.
Use a demo site only - it posts stock, invoices, journal and payment entries.
All amounts are invented sample figures; every party name is fictional.
"""

import frappe
from frappe.utils import add_days, flt, getdate, today

DONE_KEY = "sanvidhi_epc_demo_steps"
PASSWORD = "Demo@2026!"

ROADS = "Khopoli Internal Roads"
LAYOUT = "Sun Valley Farm Layout"
LAYOUT2 = "Mountain Heights Layout"
CLIENT = "Sahyadri Industrial Park Pvt Ltd"
SITE_STORE = "Khopoli Site Store"

SUPPLIERS = {
	"earthwork": "Shree Ganesh Earthmovers",
	"roads": "Sai Road Builders",
	"wall": "Konkan Masonry Works",
	"cement": "Om Cement Traders",
	"steel": "Raigad Steel Suppliers",
	"broker": "Pali Land Consultants",
}

# BOQ ref, description, uom, qty, sell rate, cost head, budget cost rate  (same lines as the pitch deck)
BOQ_LINES = [
	("1.1", "Earthwork excavation in all soils", "Cubic Meter", 1200, 180, "Subcontract", 140),
	("1.2", "PCC M10 bed below roads", "Cubic Meter", 85, 5200, "Material", 4300),
	("2.1", "Internal road, WBM in two layers", "Square Meter", 3400, 420, "Subcontract", 330),
	("2.2", "Stormwater drain, RCC precast", "Meter", 650, 1450, "Subcontract", 1150),
	("3.1", "Compound wall, stone masonry", "Meter", 900, 2800, "Subcontract", 2250),
]

PLOT_BUYERS = [
	"Anil Deshmukh", "Sunita Patil", "Rahul Joshi", "Meera Kulkarni", "Prakash Shinde",
	"Kavita Pawar", "Nilesh Gaikwad", "Swati Jadhav", "Vikram More", "Asha Bhosale",
]


# ---------------------------------------------------------------------------------------------- helpers
def _company():
	return frappe.db.get_single_value("Sanvidhi EPC Settings", "company") or frappe.db.get_value("Company", {}, "name")


def _abbr():
	return frappe.db.get_value("Company", _company(), "abbr")


def _days(n):
	"""A date n days before today (keeps the demo current whenever it is loaded)."""
	return add_days(today(), -n)


def _get_or_insert(doctype, filters, values):
	name = frappe.db.get_value(doctype, filters)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **filters, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def _project(name):
	return frappe.db.get_value("Project", {"project_name": name})


def _submit(doc):
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _done():
	return set(frappe.parse_json(frappe.db.get_default(DONE_KEY) or "[]"))


def _mark(step):
	steps = _done() | {step}
	frappe.db.set_default(DONE_KEY, frappe.as_json(sorted(steps)))


# ---------------------------------------------------------------------------------------------- step 1
def step_1_settings_and_masters():
	"""Items, UOM, warehouse, accounts and Sanvidhi EPC Settings."""
	company, abbr = _company(), _abbr()
	# bookings go back ~10 months: make sure every fiscal year from then to today exists
	from erpnext.accounts.utils import get_fiscal_year

	day = getdate(_days(320))
	while day <= getdate(today()):
		try:
			get_fiscal_year(day, company=company)
		except Exception:
			start = getdate(f"{day.year if day.month >= 4 else day.year - 1}-04-01")
			fy = frappe.get_doc(
				{"doctype": "Fiscal Year", "year": f"{start.year}-{str(start.year + 1)[2:]}",
				 "year_start_date": start, "year_end_date": add_days(f"{start.year + 1}-04-01", -1)}
			)
			fy.insert(ignore_permissions=True)
		day = add_days(day, 90)
		day = getdate(day)
	_get_or_insert("UOM", {"uom_name": "Bag"}, {"must_be_whole_number": 1})
	for code, uom, group, stock, rate in [
		("EPC Contract Service", "Nos", "Services", 0, 0),
		("EPC Client Billing", "Nos", "Services", 0, 0),
		("EPC Plot Sale", "Nos", "Services", 0, 0),
		("Cement OPC 53", "Bag", "Raw Material", 1, 380),
		("TMT Steel Fe500", "Kg", "Raw Material", 1, 62),
		("Aggregate 40mm", "Cubic Meter", "Raw Material", 1, 1450),
	]:
		_get_or_insert(
			"Item",
			{"item_code": code},
			{"item_name": code, "item_group": group, "stock_uom": uom, "is_stock_item": stock,
			 "valuation_rate": rate, "include_item_in_manufacturing": 0},
		)
	_get_or_insert(
		"Warehouse",
		{"warehouse_name": SITE_STORE, "company": company},
		{"parent_warehouse": f"All Warehouses - {abbr}"},
	)

	def account(name, root_type):
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 1, "root_type": root_type, "account_type": ""},
			"name",
			order_by="lft desc",
		)
		return _get_or_insert(
			"Account", {"account_name": name, "company": company}, {"parent_account": parent, "is_group": 0}
		)

	settings = frappe.get_single("Sanvidhi EPC Settings")
	settings.update(
		{
			"company": company,
			"contractor_service_item": "EPC Contract Service",
			"client_billing_item": "EPC Client Billing",
			"plot_sale_item": "EPC Plot Sale",
			"retention_payable_account": account("Retention Payable", "Liability"),
			"contractor_advance_account": account("Contractor Advances", "Asset"),
			"retention_receivable_account": account("Retention Receivable", "Asset"),
			"default_retention_percent": 5,
			"default_tds_percent": 2,
			"default_advance_recovery_percent": 10,
			"client_retention_percent": 5,
			"max_discount_percent": 2,
			"demand_lead_days": 7,
			"email_demand_letters": 0,
			"late_interest_percent": 12,
			"digest_enabled": 1,
			"digest_recipients": "md@srushti.demo",
			"enforce_dpr_before_material_request": 0,
		}
	)
	settings.save(ignore_permissions=True)


# ---------------------------------------------------------------------------------------------- step 2
def step_2_users():
	"""One demo user per role, all with the same password."""
	users = [
		("md@srushti.demo", "Managing Director", ["EPC MD", "Accounts Manager", "Purchase Manager", "Projects Manager",
			"Sales Manager", "Stock Manager"]),
		("pm@srushti.demo", "Project Manager", ["EPC Project Manager", "Projects User", "Purchase User", "Stock User"]),
		("site@srushti.demo", "Site Engineer", ["EPC Site Engineer", "Projects User", "Stock User", "Purchase User"]),
		("billing@srushti.demo", "Billing Engineer", ["EPC Billing Engineer", "Projects User", "Sales User"]),
		("accounts@srushti.demo", "Accounts", ["EPC Accounts User", "Accounts User", "Purchase User", "Sales User"]),
		("sales@srushti.demo", "Plot Sales", ["Plot Sales User", "Sales User"]),
	]
	for email, first_name, roles in users:
		if frappe.db.exists("User", email):
			continue
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0,
			 "new_password": PASSWORD, "user_type": "System User"}
		)
		for role in roles:
			if frappe.db.exists("Role", role):
				user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------------------------- step 3
def step_3_parties_and_projects():
	"""Client, contractors, suppliers, broker, plot buyers and the three projects."""
	company = _company()
	_get_or_insert("Customer", {"customer_name": CLIENT}, {"customer_type": "Company"})
	for buyer in PLOT_BUYERS:
		_get_or_insert(
			"Customer",
			{"customer_name": buyer},
			{"customer_type": "Individual", "email_id": buyer.lower().replace(" ", ".") + "@example.com"},
		)
	group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	for supplier in SUPPLIERS.values():
		_get_or_insert("Supplier", {"supplier_name": supplier}, {"supplier_group": group})
	client = frappe.db.get_value("Customer", {"customer_name": CLIENT})
	_get_or_insert(
		"Project",
		{"project_name": ROADS},
		{"company": company, "customer": client, "expected_start_date": _days(75), "expected_end_date": add_days(today(), 120)},
	)
	for name in (LAYOUT, LAYOUT2):
		_get_or_insert("Project", {"project_name": name}, {"company": company, "expected_start_date": _days(200)})


# ---------------------------------------------------------------------------------------------- step 4
def step_4_boq():
	"""W1: BOQ for the roads contract (₹55,48,500), submitted; budget written to the project."""
	project = _project(ROADS)
	if frappe.db.get_value("BOQ", {"project": project, "docstatus": 1}):
		return
	boq = frappe.get_doc(
		{
			"doctype": "BOQ",
			"boq_title": "Internal roads, drains and compound wall",
			"company": _company(),
			"project": project,
			"customer": frappe.db.get_value("Customer", {"customer_name": CLIENT}),
			"boq_date": _days(70),
			"items": [
				{"boq_ref": r, "description": d, "uom": u, "qty": q, "rate": rate, "cost_head": head, "cost_rate": cost}
				for r, d, u, q, rate, head, cost in BOQ_LINES
			],
		}
	)
	_submit(boq)


def _boq():
	return frappe.db.get_value("BOQ", {"project": _project(ROADS), "docstatus": 1})


def _supplier(key):
	return frappe.db.get_value("Supplier", {"supplier_name": SUPPLIERS[key]})


# ---------------------------------------------------------------------------------------------- step 5
def step_5_work_orders():
	"""W2: three contractor work orders awarded from the BOQ."""
	plan = [
		("earthwork", [("1.1", 1200, 140), ("1.2", 85, 4300)], 0, 0),
		("roads", [("2.1", 3400, 330), ("2.2", 650, 1150)], 300000, 10),
		("wall", [("3.1", 900, 2250)], 100000, 10),
	]
	for key, lines, advance, recovery in plan:
		if frappe.db.exists("Contractor Work Order", {"supplier": _supplier(key), "docstatus": 1}):
			continue
		_submit(
			frappe.get_doc(
				{
					"doctype": "Contractor Work Order",
					"company": _company(),
					"project": _project(ROADS),
					"boq": _boq(),
					"supplier": _supplier(key),
					"order_date": _days(65),
					"start_date": _days(62),
					"end_date": add_days(today(), 90),
					"mobilisation_advance": advance,
					"advance_recovery_percent": recovery,
					"items": [{"boq_ref": r, "qty": q, "rate": rate} for r, q, rate in lines],
				}
			)
		)


def _work_order(key):
	return frappe.db.get_value("Contractor Work Order", {"supplier": _supplier(key), "docstatus": 1})


# ---------------------------------------------------------------------------------------------- step 6
def step_6_site_stores():
	"""W2/W3: site material request -> purchase order -> receipt at the site store -> issue to work."""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	from erpnext.stock.doctype.material_request.material_request import make_purchase_order

	company, project = _company(), _project(ROADS)
	store = frappe.db.get_value("Warehouse", {"warehouse_name": SITE_STORE, "company": company})
	if frappe.db.exists("Stock Entry", {"project": project, "docstatus": 1}):
		return

	def material_request(lines, days_ago, submit=True):
		mr = frappe.get_doc(
			{
				"doctype": "Material Request",
				"material_request_type": "Purchase",
				"company": company,
				"transaction_date": _days(days_ago),
				"schedule_date": _days(days_ago - 3),
				"set_warehouse": store,
				"items": [
					{"item_code": i, "qty": q, "schedule_date": _days(days_ago - 3), "warehouse": store, "project": project}
					for i, q in lines
				],
			}
		)
		mr.insert(ignore_permissions=True)
		if submit:
			mr.submit()
		return mr

	for lines, supplier_key, days_ago in [
		([("Cement OPC 53", 600), ("Aggregate 40mm", 120)], "cement", 40),
		([("TMT Steel Fe500", 4000)], "steel", 30),
	]:
		mr = material_request(lines, days_ago)
		po = make_purchase_order(mr.name)
		po.supplier = _supplier(supplier_key)
		po.transaction_date = _days(days_ago - 1)
		po.schedule_date = _days(days_ago - 4)
		for row in po.items:
			row.rate = frappe.db.get_value("Item", row.item_code, "valuation_rate")
			row.schedule_date = po.schedule_date
			row.project = project
		po.insert(ignore_permissions=True)
		po.submit()
		pr = make_purchase_receipt(po.name)
		pr.set_posting_time = 1
		pr.posting_date = _days(days_ago - 4)
		pr.insert(ignore_permissions=True)
		pr.submit()

	# consumption against the work (issues tagged to the project)
	for item, qty, days_ago in [("Cement OPC 53", 420, 20), ("Aggregate 40mm", 90, 18), ("TMT Steel Fe500", 2600, 15)]:
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": company,
				"project": project,
				"set_posting_time": 1,
				"posting_date": _days(days_ago),
				"items": [{"item_code": item, "qty": qty, "s_warehouse": store, "project": project}],
			}
		)
		_submit(se)

	# one open request for the demo: the MD approves it live
	material_request([("Cement OPC 53", 300)], 1, submit=False)


# ---------------------------------------------------------------------------------------------- step 7
def _mb(mb_type, lines, days_ago, work_order=None):
	doc = frappe.get_doc(
		{
			"doctype": "Measurement Book",
			"company": _company(),
			"project": _project(ROADS),
			"boq": _boq(),
			"mb_type": mb_type,
			"contractor_work_order": work_order,
			"measurement_date": _days(days_ago),
			"period_to": _days(days_ago),
			"items": [{"boq_ref": r, "nos": 1, "qty": q, "remarks": rem} for r, q, rem in lines],
		}
	)
	return _submit(doc).name


def step_7_contractor_measurements():
	"""W3: contractor measurements over the last two months."""
	if frappe.db.exists("Measurement Book", {"project": _project(ROADS), "mb_type": "Contractor", "docstatus": 1}):
		return
	_mb("Contractor", [("1.1", 1200, "Full site, chainage 0-850"), ("1.2", 85, "Road bed")], 45, _work_order("earthwork"))
	_mb("Contractor", [("2.1", 1800, "Roads A and B, layer 1-2"), ("2.2", 300, "Drain D1")], 35, _work_order("roads"))
	_mb("Contractor", [("2.1", 1600, "Roads C and D"), ("2.2", 350, "Drain D2, D3")], 12, _work_order("roads"))
	_mb("Contractor", [("3.1", 30, "Front gate stretch")], 8, _work_order("wall"))


# ---------------------------------------------------------------------------------------------- step 8
def step_8_contractor_bills():
	"""W4: contractor RA bills - earthwork (invoiced), roads bill 1 (invoiced) and bill 2 (certified, to invoice)."""
	from sanvidhi_epc.sanvidhi_epc.doctype.contractor_ra_bill.contractor_ra_bill import (
		make_deduction_journal,
		make_purchase_invoice,
	)

	if frappe.db.exists("Contractor RA Bill", {"project": _project(ROADS), "docstatus": 1}):
		return

	def bill(key, days_ago, period_days_ago, invoice):
		doc = frappe.new_doc("Contractor RA Bill")
		doc.update(
			{"company": _company(), "contractor_work_order": _work_order(key), "bill_date": _days(days_ago),
			 "period_to": _days(period_days_ago)}
		)
		doc.get_measurements()
		_submit(doc)
		if invoice:
			pi = frappe.get_doc("Purchase Invoice", make_purchase_invoice(doc.name))
			pi.set_posting_time = 1
			pi.posting_date = pi.bill_date = _days(days_ago)
			pi.save(ignore_permissions=True)
			pi.submit()
			if doc.retention_amount or doc.advance_recovery_amount:
				je = frappe.get_doc("Journal Entry", make_deduction_journal(doc.name))
				je.posting_date = _days(days_ago)
				je.save(ignore_permissions=True)
				je.submit()
		return doc.name

	bill("earthwork", 40, 45, invoice=True)
	bill("roads", 30, 35, invoice=True)
	bill("roads", 6, 12, invoice=False)


# ---------------------------------------------------------------------------------------------- step 9
def step_9_client_billing():
	"""W5/W6: client measurements, two client RA bills; bill 1 short-certified and invoiced, bill 2 awaiting certification."""
	from sanvidhi_epc.sanvidhi_epc.doctype.client_ra_bill.client_ra_bill import make_sales_invoice

	if frappe.db.exists("Client RA Bill", {"boq": _boq(), "docstatus": 1}):
		return
	_mb("Client", [("1.1", 1200, "Joint measurement"), ("1.2", 85, "Joint measurement"),
		("2.1", 1800, "Roads A, B"), ("2.2", 300, "Drain D1")], 33)

	def client_bill(days_ago, period_days_ago):
		doc = frappe.new_doc("Client RA Bill")
		doc.update({"company": _company(), "boq": _boq(), "bill_date": _days(days_ago), "period_to": _days(period_days_ago)})
		doc.get_measurements()
		return _submit(doc)

	first = client_bill(31, 33)
	_submit(
		frappe.get_doc(
			{
				"doctype": "Certification",
				"client_ra_bill": first.name,
				"certification_date": _days(24),
				"certified_by": "Er. S. Kale, client engineer",
				"client_reference": "SIP/CERT/01",
				"certified_amount": flt(first.current_value) - 37800,
				"reason_for_difference": "WBM on Road B chainage 200-290 to be re-rolled before acceptance",
			}
		)
	)
	si = frappe.get_doc("Sales Invoice", make_sales_invoice(first.name))
	si.set_posting_time = 1
	si.posting_date = _days(23)
	si.due_date = add_days(si.posting_date, 30)
	si.set("payment_schedule", [])
	si.save(ignore_permissions=True)
	si.submit()

	_mb("Client", [("2.1", 1600, "Roads C, D"), ("2.2", 350, "Drains D2, D3"), ("3.1", 30, "Front gate stretch")], 7)
	client_bill(5, 7)


# ---------------------------------------------------------------------------------------------- step 10
def step_10_daily_reports():
	"""W8: a DPR for each of the last 8 days at Khopoli (two rain days); digests for yesterday and today."""
	project = _project(ROADS)
	for n in range(7, -1, -1):
		day = _days(n)
		if frappe.db.exists("Daily Progress Report", {"project": project, "report_date": day, "docstatus": ["<", 2]}):
			continue
		rain = n in (3, 4)
		_submit(
			frappe.get_doc(
				{
					"doctype": "Daily Progress Report",
					"company": _company(),
					"project": project,
					"report_date": day,
					"site_location": "Khopoli, Road C",
					"weather": "Rain" if rain else "Clear",
					"work_done": [
						{"boq_ref": "2.1", "description": "WBM layer 2, Road C", "uom": "Square Meter", "qty_done": 0 if rain else 140},
						{"boq_ref": "3.1", "description": "Compound wall, stone masonry", "uom": "Meter", "qty_done": 0 if rain else 6},
					],
					"labour": [
						{"category": "Mason", "supplier": _supplier("wall"), "count": 6},
						{"category": "Helper", "supplier": _supplier("roads"), "count": 18 if not rain else 6},
						{"category": "Operator", "supplier": _supplier("roads"), "count": 3},
					],
					"machinery": [{"equipment": "Vibratory roller 10T", "hours": 0 if rain else 7.5, "fuel_litres": 0 if rain else 60}],
					"hindrances": "Rain from 11 am; rolling stopped" if rain else "",
					"next_day_plan": "Continue WBM layer 2 on Road C; wall footing at north side",
				}
			)
		)
	from sanvidhi_epc.tasks.digest import build_digest

	for n in (1, 0):
		build_digest(_days(n))


# ---------------------------------------------------------------------------------------------- step 11
def step_11_plots():
	"""Plot master: 18 plots in Sun Valley Farm and 6 in Mountain Heights."""
	sizes = [3200, 3500, 4000, 3500, 4500, 3200, 5000, 3500, 4000, 3200, 3500, 8000, 4000, 3500, 3200, 4500, 3500, 21800]
	layout = _project(LAYOUT)
	for i, area in enumerate(sizes, start=1):
		_get_or_insert(
			"Plot",
			{"layout": layout, "plot_no": f"P-{i:02d}"},
			{"area_sqft": area, "rate_per_sqft": 480 if area < 8000 else 140,
			 "plot_type": "Agricultural" if area >= 8000 else "Residential",
			 "facing": ["East", "West", "North", "South"][i % 4], "survey_no": f"Gat {112 + i // 6}"},
		)
	layout2 = _project(LAYOUT2)
	for i in range(1, 7):
		_get_or_insert(
			"Plot",
			{"layout": layout2, "plot_no": f"MH-{i:02d}"},
			{"area_sqft": 3500, "rate_per_sqft": 520, "plot_type": "Residential", "facing": "East"},
		)


# ---------------------------------------------------------------------------------------------- step 12
def _booking(plot_no, buyer, days_ago, discount=0, broker=False):
	plot = frappe.db.get_value("Plot", {"layout": _project(LAYOUT), "plot_no": plot_no})
	if frappe.db.get_value("Plot", plot, "status") != "Available":
		return frappe.db.get_value("Plot", plot, "plot_booking")
	area, rate = frappe.db.get_value("Plot", plot, ["area_sqft", "rate_per_sqft"])
	agreed = flt(area * rate * (1 - discount / 100), 2)
	start = _days(days_ago)
	schedule = [("Booking", 0, 0.10), ("Agreement", 30, 0.20), ("Road and drainage complete", 120, 0.30), ("Registration", 240, 0.40)]
	rows, used = [], 0
	for i, (milestone, offset, share) in enumerate(schedule):
		amount = flt(agreed * share, 2) if i < len(schedule) - 1 else flt(agreed - used, 2)
		used += amount
		rows.append({"milestone": milestone, "due_date": add_days(start, offset), "amount": amount})
	doc = frappe.get_doc(
		{
			"doctype": "Plot Booking",
			"company": _company(),
			"plot": plot,
			"customer": frappe.db.get_value("Customer", {"customer_name": buyer}),
			"booking_date": start,
			"rate_per_sqft": rate,
			"discount_percent": discount,
			"token_amount": rows[0]["amount"],
			"broker": _supplier("broker") if broker else None,
			"broker_commission_percent": 1 if broker else 0,
			"payment_schedule": rows,
		}
	)
	if discount > flt(frappe.db.get_single_value("Sanvidhi EPC Settings", "max_discount_percent")):
		frappe.set_user("md@srushti.demo")  # above the limit: the MD submits (and is recorded as approver)
	try:
		return _submit(doc).name
	finally:
		frappe.set_user("Administrator")


def _receive(booking, amount, days_ago, ref):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	so = frappe.db.get_value("Plot Booking", booking, "sales_order")
	pe = get_payment_entry("Sales Order", so)
	pe.posting_date = _days(days_ago)
	pe.paid_amount = pe.received_amount = amount
	pe.references[0].allocated_amount = amount
	pe.reference_no, pe.reference_date = ref, _days(days_ago)
	_submit(pe)


def _sales_order(booking):
	from sanvidhi_epc.sanvidhi_epc.doctype.plot_booking.plot_booking import make_sales_order

	so = frappe.get_doc("Sales Order", make_sales_order(booking))
	if so.docstatus == 0:
		so.submit()
	return so.name


def step_12_plot_sales():
	"""W6/W7: 7 plots sold (paid in full, handed over), 3 booked with instalments running, the rest open."""
	from sanvidhi_epc.utils.collections import refresh_booking

	if frappe.db.exists("Plot Booking", {"layout": _project(LAYOUT), "docstatus": 1}):
		return
	sold = [("P-01", 0), ("P-02", 1), ("P-04", 2), ("P-08", 3), ("P-11", 4), ("P-14", 5), ("P-16", 6)]
	for plot_no, i in sold:
		booking = _booking(plot_no, PLOT_BUYERS[i], 300 - i * 10, broker=i % 2 == 0)
		_sales_order(booking)
		agreed = frappe.db.get_value("Plot Booking", booking, "agreed_value")
		_receive(booking, flt(agreed * 0.3, 2), 290 - i * 10, f"NEFT{1000 + i}")
		_receive(booking, flt(agreed, 2) - flt(agreed * 0.3, 2), 60 - i * 5, f"NEFT{2000 + i}")
		handover = frappe.new_doc("Plot Handover")
		handover.update(
			{"company": _company(), "plot_booking": booking, "handover_date": _days(50 - i * 5),
			 "registration_date": _days(52 - i * 5), "registration_no": f"KPL/{2026}/{4400 + i}",
			 "sub_registrar_office": "Sub-Registrar, Khalapur"}
		)
		handover.insert(ignore_permissions=True)
		for d in handover.documents:
			d.received = 1
		handover.save(ignore_permissions=True)
		handover.submit()

	# booked: one on time, one with an overdue instalment, one booked last week with a 5% discount (MD-approved)
	booked = [("P-03", 7, 115, 0, [(0.10, 113), (0.20, 85)]), ("P-07", 8, 160, 0, [(0.10, 158)]),
		("P-12", 9, 6, 5, [(0.10, 5)])]
	for plot_no, i, days_ago, discount, receipts in booked:
		booking = _booking(plot_no, PLOT_BUYERS[i], days_ago, discount=discount)
		_sales_order(booking)
		agreed = frappe.db.get_value("Plot Booking", booking, "agreed_value")
		for n, (share, paid_days_ago) in enumerate(receipts):
			_receive(booking, flt(agreed * share, 2), paid_days_ago, f"UPI{3000 + i}{n}")
		refresh_booking(booking)

	# one blocked plot (held back by the partners)
	plot = frappe.get_doc("Plot", {"layout": _project(LAYOUT), "plot_no": "P-18"})
	plot.status = "Blocked"
	plot.save(ignore_permissions=True)


# ---------------------------------------------------------------------------------------------- step 13
def step_13_demand_letters():
	"""W7: P-07's road milestone demanded with the unpaid agreement instalment and late interest; daily job drafts the rest."""
	booking = frappe.db.get_value(
		"Plot Booking", {"plot": frappe.db.get_value("Plot", {"layout": _project(LAYOUT), "plot_no": "P-07"})}
	)
	if booking and not frappe.db.exists("Demand Letter", {"plot_booking": booking}):
		agreement_due = frappe.db.get_value(
			"Plot Payment Schedule", {"parent": booking, "milestone": "Agreement"}, "due_date"
		)
		# issued on time for the agreement instalment, which the buyer has not paid ...
		for milestone, letter_date in [("Agreement", add_days(agreement_due, -7)), ("Road and drainage complete", today())]:
			# ... so today's letter for the road milestone carries it forward with late interest
			_submit(
				frappe.get_doc(
					{"doctype": "Demand Letter", "company": _company(), "plot_booking": booking,
					 "milestone": milestone, "letter_date": letter_date}
				)
			)
	frappe.get_attr("sanvidhi_epc.tasks.demand.daily")()


STEPS = [
	step_1_settings_and_masters,
	step_2_users,
	step_3_parties_and_projects,
	step_4_boq,
	step_5_work_orders,
	step_6_site_stores,
	step_7_contractor_measurements,
	step_8_contractor_bills,
	step_9_client_billing,
	step_10_daily_reports,
	step_11_plots,
	step_12_plot_sales,
	step_13_demand_letters,
]


def run(step=None, force=False):
	"""Run all steps in order (skipping finished ones), or one step by number."""
	frappe.set_user("Administrator")
	if not _company():
		frappe.throw("Complete the ERPNext setup wizard first: no company found")
	selected = [STEPS[int(step) - 1]] if step else STEPS
	done = _done()
	for fn in selected:
		number = STEPS.index(fn) + 1
		if number in done and not (step or force):
			print(f"  skip  {number:>2}. {fn.__doc__.splitlines()[0]}")
			continue
		try:
			fn()
			_mark(number)
			frappe.db.commit()
			print(f"  done  {number:>2}. {fn.__doc__.splitlines()[0]}")
		except Exception:
			frappe.db.rollback()
			print(f"  FAIL  {number:>2}. {fn.__doc__.splitlines()[0]}")
			raise
	print(f"\nDemo users: md@ / pm@ / site@ / billing@ / accounts@ / sales@srushti.demo  password: {PASSWORD}")


def status():
	done = _done()
	for i, fn in enumerate(STEPS, start=1):
		print(f"  {'done' if i in done else '    '}  {i:>2}. {fn.__doc__.splitlines()[0]}")
