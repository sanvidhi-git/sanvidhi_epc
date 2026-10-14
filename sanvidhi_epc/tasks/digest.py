"""Workflow 8: the evening digest - every open site's progress report in one email to the partners."""

import frappe
from frappe import _
from frappe.utils import cint, escape_html, getdate, now_datetime, today

from sanvidhi_epc.utils.settings import get_settings


def scheduled():
	settings = get_settings()
	if not settings.digest_enabled:
		return
	digest = build_digest(today())
	if digest.recipients:
		send_digest(digest.name)


def build_digest(digest_date):
	digest_date = getdate(digest_date)
	name = frappe.db.get_value("Daily Digest", {"digest_date": digest_date})
	digest = frappe.get_doc("Daily Digest", name) if name else frappe.new_doc("Daily Digest")
	digest.digest_date = digest_date
	if not digest.recipients:
		digest.recipients = get_settings().digest_recipients
	digest.set("sites", [])

	projects = frappe.get_all("Project", filters={"status": "Open"}, fields=["name", "project_name"], order_by="name")
	blocks = []
	for project in projects:
		dpr_name = frappe.db.get_value(
			"Daily Progress Report", {"project": project.name, "report_date": digest_date, "docstatus": 1}
		)
		if not dpr_name:
			digest.append("sites", {"project": project.name, "status": "Missing"})
			blocks.append(
				f"<h4>{escape_html(project.project_name or project.name)}</h4>"
				f"<p style='color:#b54708'>{_('No progress report submitted')}</p>"
			)
			continue
		dpr = frappe.get_doc("Daily Progress Report", dpr_name)
		digest.append(
			"sites",
			{
				"project": project.name,
				"daily_progress_report": dpr.name,
				"status": "Reported",
				"labour_count": cint(dpr.total_labour),
				"work_items": len(dpr.work_done),
				"hindrances": dpr.hindrances,
			},
		)
		work = ""
		for w in dpr.work_done:
			qty = " - {:g} {}".format(w.qty_done, escape_html(w.uom or "")) if w.qty_done else ""
			work += "<li>{}{}</li>".format(escape_html(w.description or ""), qty)
		weather = " · {}: {}".format(_("Weather"), escape_html(dpr.weather)) if dpr.weather else ""
		block = "<h4>{}</h4><p>{}: <b>{}</b>{}</p><ul>{}</ul>".format(
			escape_html(project.project_name or project.name), _("Headcount"), cint(dpr.total_labour), weather, work
		)
		if dpr.hindrances:
			block += "<p><b>{}:</b> {}</p>".format(_("Hindrances"), escape_html(dpr.hindrances))
		if dpr.next_day_plan:
			block += "<p><b>{}:</b> {}</p>".format(_("Tomorrow"), escape_html(dpr.next_day_plan))
		blocks.append(block)

	digest.sites_reported = sum(1 for s in digest.sites if s.status == "Reported")
	digest.sites_missing = sum(1 for s in digest.sites if s.status == "Missing")
	header = (
		f"<p>{_('Sites reported')}: <b>{digest.sites_reported}</b> &nbsp; "
		f"{_('Missing')}: <b>{digest.sites_missing}</b></p>"
	)
	digest.summary_html = header + "".join(blocks)
	digest.flags.ignore_permissions = True
	digest.save()
	return digest


def send_digest(name):
	digest = frappe.get_doc("Daily Digest", name)
	recipients = [r.strip() for r in (digest.recipients or "").replace(",", "\n").splitlines() if r.strip()]
	if not recipients:
		frappe.throw(_("Add recipients to the digest or to Sanvidhi EPC Settings"))
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Site digest for {0}").format(frappe.format(digest.digest_date, {"fieldtype": "Date"})),
			message=digest.summary_html,
			reference_doctype="Daily Digest",
			reference_name=digest.name,
		)
		digest.db_set({"status": "Sent", "sent_on": now_datetime()})
	except Exception:
		digest.db_set("status", "Failed")
		frappe.log_error(title=f"Daily Digest {digest.name} not sent")
