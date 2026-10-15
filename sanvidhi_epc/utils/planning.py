"""Standard ERPNext project management, driven by the EPC documents.

* BOQ submit      -> the "EPC Site" template's stages (if the project has no tasks) and one Task per BOQ line
                     under its "Execution" group, weighted by the line's value; the project's % complete is the
                     BOQ's value-weighted figure (method "Manual", written on every refresh).
* Work order      -> task start / end dates from the work orders awarded against the line.
* Client MB       -> task progress = client-measured qty / BOQ qty; Working / Completed status and actual dates.
* DPR submit      -> a Timesheet of the day's labour on the project: hours for every crew, cost only for own
                     (departmental) labour, since contractor labour is paid through RA bills.
* Any cost document on the project -> the BOQ's "Progress and Margin to Date" section is recomputed:
                     value of work done (earned value) against actual cost, not ERPNext's billed-minus-cost.

Like utils/progress.py, every figure is recomputed from submitted documents, never incremented.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime

from sanvidhi_epc.utils.settings import get_settings

EXECUTION = "Execution"
CONTRACTOR_LABOUR = "Contractor Labour"
LABOUR_PREFIX = "Site Labour - "

# hourly cost of own (departmental) labour; editable afterwards on each Activity Type
LABOUR_RATES = {
	"Mason": 110,
	"Helper": 70,
	"Carpenter": 100,
	"Bar Bender": 100,
	"Operator": 120,
	"Electrician": 110,
	"Supervisor": 160,
	"Other": 70,
}

# Project Template "EPC Site": (subject, start offset days, duration days, is_group, depends on)
TEMPLATE = "EPC Site"
TEMPLATE_TASKS = [
	("Mobilisation and site setup", 0, 15, 0, None),
	(EXECUTION, 10, 150, 1, "Mobilisation and site setup"),
	("Quality checks and snag list", 150, 20, 0, EXECUTION),
	("Handover to client", 170, 10, 0, "Quality checks and snag list"),
]


# ------------------------------------------------------------------------------------------- setup
def setup_masters():
	"""Custom fields, activity types and the EPC Site project template (idempotent, run on migrate)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Task": [
				{"fieldname": "boq", "label": "BOQ", "fieldtype": "Link", "options": "BOQ", "insert_after": "project",
				 "read_only": 1, "no_copy": 1},
				{"fieldname": "boq_ref", "label": "BOQ Ref", "fieldtype": "Data", "insert_after": "boq", "read_only": 1,
				 "no_copy": 1, "in_standard_filter": 1},
			],
			"Timesheet": [
				{"fieldname": "daily_progress_report", "label": "Daily Progress Report", "fieldtype": "Link",
				 "options": "Daily Progress Report", "insert_after": "parent_project", "read_only": 1, "no_copy": 1},
			],
		},
		update=True,
	)
	for category, rate in LABOUR_RATES.items():
		if not frappe.db.exists("Activity Type", LABOUR_PREFIX + category):
			frappe.get_doc(
				{"doctype": "Activity Type", "activity_type": LABOUR_PREFIX + category, "costing_rate": rate}
			).insert(ignore_permissions=True)
	if not frappe.db.exists("Activity Type", CONTRACTOR_LABOUR):
		frappe.get_doc({"doctype": "Activity Type", "activity_type": CONTRACTOR_LABOUR, "costing_rate": 0}).insert(
			ignore_permissions=True
		)
	setup_project_template()
	grant_project_permissions()
	# sites upgraded from an earlier version: switch the new features on once (fresh installs get the defaults)
	for field, value in (("create_tasks_from_boq", 1), ("create_labour_timesheets", 1), ("default_labour_hours", 8)):
		if not frappe.db.sql(
			"select 1 from `tabSingles` where doctype = 'Sanvidhi EPC Settings' and field = %s", field
		):
			frappe.db.set_single_value("Sanvidhi EPC Settings", field, value)


# EPC roles on ERPNext's project doctypes, so the team does not also need "Projects User"
R, W, C, S, X = "read", "write", "create", "submit", "cancel"
PROJECT_PERMISSIONS = {
	"Project": {"EPC MD": [R, W, "report"], "EPC Project Manager": [R, W, C, "report"], "EPC Site Engineer": [R],
		"EPC Billing Engineer": [R], "EPC Accounts User": [R, "report"]},
	"Task": {"EPC MD": [R, W, "report"], "EPC Project Manager": [R, W, C, "report"], "EPC Site Engineer": [R, W],
		"EPC Billing Engineer": [R]},
	"Timesheet": {"EPC MD": [R, "report"], "EPC Project Manager": [R, W, C, S, X, "report"],
		"EPC Site Engineer": [R], "EPC Accounts User": [R, "report"]},
	"Project Template": {"EPC MD": [R], "EPC Project Manager": [R, W, C]},
	"Activity Type": {"EPC MD": [R, W], "EPC Project Manager": [R, W], "EPC Site Engineer": [R],
		"EPC Accounts User": [R]},
}


def grant_project_permissions():
	"""Add each rule once; a rule an administrator has since changed or removed is left as it is."""
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	from frappe.permissions import add_permission, update_permission_property

	done = set(frappe.parse_json(frappe.db.get_default("sanvidhi_epc_project_perms") or "[]"))
	for doctype, roles in PROJECT_PERMISSIONS.items():
		changed = False
		for role, rights in roles.items():
			key = f"{doctype}|{role}"
			if key in done or not frappe.db.exists("Role", role):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role, 0, R)
			for right in rights:
				update_permission_property(doctype, role, 0, right, 1, validate=False)
			done.add(key)
			changed = True
		if changed:
			validate_permissions_for_doctype(doctype)
			frappe.clear_cache(doctype=doctype)
	frappe.db.set_default("sanvidhi_epc_project_perms", frappe.as_json(sorted(done)))


def setup_project_template():
	if frappe.db.exists("Project Template", TEMPLATE):
		return
	names = {}
	for subject, start, duration, is_group, _dep in TEMPLATE_TASKS:
		name = frappe.db.get_value("Task", {"subject": subject, "is_template": 1})
		if not name:
			task = frappe.get_doc(
				{"doctype": "Task", "subject": subject, "is_template": 1, "start": start, "duration": duration,
				 "is_group": is_group}
			)
			task.insert(ignore_permissions=True)
			name = task.name
		names[subject] = name
	for subject, _s, _d, _g, dep in TEMPLATE_TASKS:
		if dep:
			task = frappe.get_doc("Task", names[subject])
			if not task.depends_on:
				task.append("depends_on", {"task": names[dep]})
				task.save(ignore_permissions=True)
	if not frappe.db.exists("Project Type", "EPC"):
		frappe.get_doc({"doctype": "Project Type", "project_type": "EPC"}).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Project Template",
			"name": TEMPLATE,
			"project_type": "EPC",
			"tasks": [{"task": names[s], "subject": s} for s, *_ in TEMPLATE_TASKS],
		}
	).insert(ignore_permissions=True, set_name=TEMPLATE)
	settings = frappe.get_single("Sanvidhi EPC Settings")
	if not settings.epc_project_template:
		settings.db_set("epc_project_template", TEMPLATE)


# ------------------------------------------------------------------------------------------- tasks
def _clamp(date, project):
	start, end = frappe.db.get_value("Project", project, ["expected_start_date", "expected_end_date"])
	date = getdate(date)
	if start and date < getdate(start):
		date = getdate(start)
	if end and date > getdate(end):
		date = getdate(end)
	return date


def apply_project_template(project):
	"""Stages from the EPC project template, when the project has no tasks yet."""
	template = get_settings().epc_project_template
	if not template or frappe.db.exists("Task", {"project": project}):
		return
	doc = frappe.get_doc("Project", project)
	doc.project_template = template
	frappe.db.savepoint("epc_template")
	try:
		doc.copy_from_template()
		doc.db_update()
	except frappe.ValidationError as e:
		# e.g. no default holiday list, or a template longer than the project's dates: BOQ tasks still come
		frappe.db.rollback(save_point="epc_template")
		frappe.clear_last_message()
		frappe.msgprint(
			_("Stages from project template {0} were not created: {1}. Only BOQ line tasks were made.").format(
				template, frappe.utils.strip_html(str(e))
			),
			indicator="orange",
			alert=True,
		)


def _execution_group(project):
	return frappe.db.get_value("Task", {"project": project, "is_group": 1, "subject": EXECUTION})


def _line_dates(boq):
	"""Earliest start and latest end of the work orders awarded against each BOQ line."""
	rows = frappe.db.sql(
		"""select i.boq_item, min(w.start_date) as start, max(w.end_date) as end
		from `tabContractor Work Order Item` i join `tabContractor Work Order` w on w.name = i.parent
		where w.docstatus = 1 and w.boq = %s group by i.boq_item""",
		boq,
		as_dict=True,
	)
	return {r.boq_item: r for r in rows}


def sync_boq_tasks(boq):
	"""Create or update one Task per BOQ line (called on BOQ submit; keeps tasks across BOQ revisions)."""
	if not cint(get_settings().create_tasks_from_boq):
		return
	boq = frappe.get_doc("BOQ", boq) if isinstance(boq, str) else boq
	project = boq.project
	apply_project_template(project)
	# % complete is written from the BOQ (value of client-measured work / contract value) in refresh_actuals:
	# ERPNext's "Task Weight" method rounds each task's share to 2 decimals and drifts from the BOQ figure
	frappe.db.set_value("Project", project, "percent_complete_method", "Manual")
	group = _execution_group(project)
	total = flt(boq.total_contract_value) or 1
	dates = _line_dates(boq.name)
	project_end = frappe.db.get_value("Project", project, "expected_end_date")
	default_end = project_end or add_days(boq.boq_date, 180)
	plan = []
	for row in boq.items:
		d = dates.get(row.name)
		start = _clamp(d.start if d and d.start else boq.boq_date, project)
		end = _clamp(d.end if d and d.end else default_end, project)
		plan.append((row, start, max(start, end)))
	if group and plan:
		# the group must span its children, or the children's dates fail validation
		g_start, g_end = frappe.db.get_value("Task", group, ["exp_start_date", "exp_end_date"])
		lo, hi = min(p[1] for p in plan), max(p[2] for p in plan)
		frappe.db.set_value(
			"Task", group,
			{"exp_start_date": min(getdate(g_start), lo) if g_start else lo,
			 "exp_end_date": max(getdate(g_end), hi) if g_end else hi},
			update_modified=False,
		)

	seen = set()
	for row, start, end in plan:
		name = frappe.db.get_value("Task", {"project": project, "boq_ref": row.boq_ref})
		task = frappe.get_doc("Task", name) if name else frappe.new_doc("Task")
		task.update(
			{
				"project": project,
				"subject": f"{row.boq_ref} {row.description}"[:140],
				"boq": boq.name,
				"boq_ref": row.boq_ref,
				"task_weight": flt(flt(row.amount) / total * 100, 4),
				"exp_start_date": start,
				"exp_end_date": end,
				"description": _("{0} {1} @ {2} (BOQ {3})").format(
					flt(row.qty), row.uom or "", flt(row.rate), boq.name
				),
			}
		)
		if group and not task.parent_task:
			task.parent_task = group
		if task.status == "Cancelled":
			task.status = "Open"
		task.flags.ignore_permissions = True
		task.save()
		seen.add(row.boq_ref)
	# lines dropped in a revision stop counting towards % complete
	for name in frappe.get_all(
		"Task", filters={"project": project, "boq_ref": ["not in", list(seen) or [""]], "boq": ["is", "set"]}, pluck="name"
	):
		frappe.db.set_value("Task", name, {"task_weight": 0, "status": "Cancelled"})
	update_task_progress(boq.name)


def update_task_schedule(boq):
	"""Work order dates onto the BOQ tasks (called when work orders are submitted or cancelled)."""
	if frappe.db.get_value("BOQ", boq, "docstatus") == 1 and cint(get_settings().create_tasks_from_boq):
		sync_boq_tasks(boq)


def update_task_progress(boq):
	"""Client-measured progress of each BOQ line onto its task; the project's % complete follows."""
	if not cint(get_settings().create_tasks_from_boq):
		return
	project = frappe.db.get_value("BOQ", boq, "project")
	measured = {
		r.boq_item: r
		for r in frappe.db.sql(
			"""select c.boq_item, min(p.measurement_date) as first, max(p.measurement_date) as last
			from `tabMeasurement Book Item` c join `tabMeasurement Book` p on p.name = c.parent
			where p.docstatus = 1 and p.mb_type = 'Client' and p.boq = %s group by c.boq_item""",
			boq,
			as_dict=True,
		)
	}
	weighted, weights = 0, 0
	for row in frappe.get_all(
		"BOQ Item", filters={"parent": boq, "parenttype": "BOQ"}, fields=["name", "boq_ref", "qty", "executed_qty", "amount"]
	):
		progress = min(100, flt(flt(row.executed_qty) / flt(row.qty) * 100, 2)) if flt(row.qty) else 0
		weighted += progress * flt(row.amount)
		weights += flt(row.amount)
		name = frappe.db.get_value("Task", {"project": project, "boq_ref": row.boq_ref})
		if not name:
			continue
		task = frappe.get_doc("Task", name)
		m = measured.get(row.name)
		status = "Completed" if progress >= 100 else ("Working" if progress > 0 else "Open")
		if task.status == "Overdue" and status == "Open":
			status = "Overdue"
		values = {
			"progress": progress,
			"status": status,
			"act_start_date": _clamp(m.first, project) if m else None,
			"act_end_date": _clamp(m.last, project) if m and progress >= 100 else None,
			"completed_on": (m.last if m else None) if progress >= 100 else None,
		}
		task.update(values)
		task.flags.ignore_permissions = True
		task.save()
	group = _execution_group(project)
	if group and weights:
		progress = flt(weighted / weights, 2)
		frappe.db.set_value(
			"Task",
			group,
			{"progress": progress, "status": "Completed" if progress >= 100 else ("Working" if progress else "Open")},
			update_modified=False,
		)
	refresh_project(project)


def refresh_project(project):
	if not project:
		return
	doc = frappe.get_doc("Project", project)
	doc.update_percent_complete()
	doc.update_costing()
	doc.db_update()


# ------------------------------------------------------------------------------------------- DPR -> Timesheet
def make_labour_timesheet(dpr):
	"""Submitted Timesheet of the day's crews: one row per labour line, cost only for own labour."""
	settings = get_settings()
	if not cint(settings.create_labour_timesheets) or dpr.timesheet:
		return
	rows = [r for r in dpr.labour if cint(r.count) > 0]
	if not rows:
		return
	default_hours = flt(settings.default_labour_hours) or 8
	start = get_datetime(f"{dpr.report_date} 08:00:00")
	ts = frappe.new_doc("Timesheet")
	ts.update(
		{
			"company": dpr.company,
			"parent_project": dpr.project,
			"daily_progress_report": dpr.name,
			"note": _("Labour from Daily Progress Report {0}").format(dpr.name),
		}
	)
	for r in rows:
		hours = flt(r.hours) or default_hours
		own = not r.supplier
		activity = LABOUR_PREFIX + r.category if own else CONTRACTOR_LABOUR
		if own and not frappe.db.exists("Activity Type", activity):
			activity = LABOUR_PREFIX + "Other"
		rate = flt(frappe.db.get_value("Activity Type", activity, "costing_rate"))
		ts.append(
			"time_logs",
			{
				"activity_type": activity,
				"from_time": start,
				"to_time": start + timedelta(hours=hours),
				"hours": hours,
				"project": dpr.project,
				"is_billable": 0,
				# a crew: the row is one shift, costed at the crew's rate
				"costing_rate": rate * cint(r.count),
				"description": _("{0} × {1}, {2} h each = {3} man-hours{4}").format(
					cint(r.count), _(r.category), flt(hours), flt(hours * cint(r.count)),
					" ({})".format(frappe.db.get_value("Supplier", r.supplier, "supplier_name")) if r.supplier else _(" (own)"),
				),
			},
		)
	ts.flags.ignore_permissions = True
	ts.insert()
	ts.submit()
	dpr.db_set("timesheet", ts.name)


def cancel_labour_timesheet(dpr):
	if dpr.timesheet and frappe.db.get_value("Timesheet", dpr.timesheet, "docstatus") == 1:
		ts = frappe.get_doc("Timesheet", dpr.timesheet)
		ts.flags.ignore_permissions = True
		ts.cancel()
	dpr.db_set("timesheet", None)


# ------------------------------------------------------------------------------------------- margin
def active_boq(project):
	return frappe.db.get_value("BOQ", {"project": project, "docstatus": 1, "status": "Active"})


def refresh_actuals(boq):
	"""Progress and margin to date on the BOQ, from the project's submitted documents."""
	doc = frappe.db.get_value("BOQ", boq, ["project", "total_contract_value"], as_dict=True)
	project = doc.project
	vowd, bcwd = 0, 0
	for r in frappe.get_all(
		"BOQ Item", filters={"parent": boq, "parenttype": "BOQ"}, fields=["executed_qty", "rate", "cost_rate"]
	):
		vowd += flt(r.executed_qty) * flt(r.rate)
		bcwd += flt(r.executed_qty) * flt(r.cost_rate)

	def one(sql, *args):
		return flt(frappe.db.sql(sql, args)[0][0])

	billed = one("select sum(current_value) from `tabClient RA Bill` where docstatus = 1 and boq = %s", boq)
	subcontract = one(
		"select sum(current_value) from `tabContractor RA Bill` where docstatus = 1 and project = %s", project
	)
	material = one(
		"""select sum(d.amount) from `tabStock Entry Detail` d join `tabStock Entry` s on s.name = d.parent
		where s.docstatus = 1 and ifnull(d.s_warehouse, '') != '' and ifnull(d.t_warehouse, '') = ''
		and ifnull(d.project, s.project) = %s""",
		project,
	)
	labour = one(
		"""select sum(d.base_costing_amount) from `tabTimesheet Detail` d join `tabTimesheet` t on t.name = d.parent
		where t.docstatus = 1 and d.project = %s""",
		project,
	)
	other = one(
		"""select sum(d.base_net_amount) from `tabPurchase Invoice Item` d
		join `tabPurchase Invoice` p on p.name = d.parent
		join `tabItem` i on i.name = d.item_code
		where p.docstatus = 1 and i.is_stock_item = 0 and ifnull(d.project, p.project) = %s
		and p.name not in (select purchase_invoice from `tabContractor RA Bill`
			where docstatus = 1 and ifnull(purchase_invoice, '') != '')""",
		project,
	)
	actual = subcontract + material + labour + other
	margin = vowd - actual
	percent = flt(vowd / flt(doc.total_contract_value) * 100, 2) if flt(doc.total_contract_value) else 0
	if cint(get_settings().create_tasks_from_boq):
		frappe.db.set_value("Project", project, "percent_complete", percent, update_modified=False)
	frappe.db.set_value(
		"BOQ",
		boq,
		{
			"percent_complete": percent,
			"value_of_work_done": vowd,
			"budgeted_cost_of_work_done": bcwd,
			"billed_to_date": billed,
			"actual_subcontract_cost": subcontract,
			"actual_material_cost": material,
			"actual_labour_cost": labour,
			"actual_other_cost": other,
			"actual_cost": actual,
			"margin_on_work_done": margin,
			"margin_on_work_done_percent": flt(margin / vowd * 100, 2) if vowd else 0,
			"cost_variance": bcwd - actual,
			"actuals_updated_on": now_datetime(),
		},
		update_modified=False,
	)


def refresh_project_actuals(project):
	boq = active_boq(project) if project else None
	if boq:
		refresh_actuals(boq)


def on_cost_document(doc, method=None):
	"""doc_events hook for Stock Entry, Timesheet and Purchase Invoice: refresh the BOQ margin of each project."""
	projects = {doc.get("project"), doc.get("parent_project")}
	for table in ("items", "time_logs"):
		for row in doc.get(table) or []:
			projects.add(row.get("project"))
	for project in filter(None, projects):
		try:
			refresh_project_actuals(project)
		except Exception:
			frappe.log_error(title=f"Sanvidhi EPC: margin refresh for {project}")


def daily():
	"""Scheduler: keep every active BOQ's progress and margin current."""
	for boq in frappe.get_all("BOQ", filters={"docstatus": 1, "status": "Active"}, pluck="name"):
		try:
			refresh_actuals(boq)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Sanvidhi EPC: margin refresh for {boq}")
