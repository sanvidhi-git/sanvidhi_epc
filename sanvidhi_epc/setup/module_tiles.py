"""Icon grid shown at the top of the Sanvidhi EPC workspace.

Every app (document type) has its own solid desktop icon under
public/icons/desktop_icons/solid/, so the site, billing and sales teams reach
each one from a single screen.
"""

import os

import frappe

GROUPS = [
	(
		"Estimate & Award",
		[
			("BOQ", "boq", "Tender to budget"),
			("Contractor Work Order", "contractor_work_order", "Award work"),
		],
	),
	(
		"Measure & Bill",
		[
			("Measurement Book", "measurement_book", "Measure work"),
			("Contractor RA Bill", "contractor_ra_bill", "Pay contractors"),
			("Client RA Bill", "client_ra_bill", "Bill the client"),
			("Certification", "certification", "Client certifies"),
		],
	),
	(
		"Site Reporting",
		[
			("Daily Progress Report", "daily_progress_report", "Day at site"),
			("Daily Digest", "daily_digest", "Evening summary"),
		],
	),
	(
		"Plot Sales",
		[
			("Plot", "plot", "Layout inventory"),
			("Plot Booking", "plot_booking", "Book and schedule"),
			("Demand Letter", "demand_letter", "Collect dues"),
			("Plot Handover", "plot_handover", "Possession"),
		],
	),
	("Setup", [("Sanvidhi EPC Settings", "sanvidhi_epc_settings", "Defaults")]),
]


def _icon(name):
	path = frappe.get_app_path("sanvidhi_epc", "public", "icons", "desktop_icons", "solid", f"{name}.svg")
	return f"/assets/sanvidhi_epc/icons/desktop_icons/solid/{name}.svg" if os.path.exists(path) else None


def tiles_html():
	def tile(label, icon, sub):
		img = f'<img src="{_icon(icon)}" alt="">' if _icon(icon) else '<span class="se-ph"></span>'
		route = "/desk/" + label.lower().replace(" ", "-")
		return (
			f'<a class="se-tile" href="{route}">{img}<span class="se-label">{label}</span>'
			f'<span class="se-sub">{sub}</span></a>'
		)

	groups = "".join(
		f'<div class="se-group">{title}</div><div class="se-grid">{"".join(tile(*t) for t in tiles)}</div>'
		for title, tiles in GROUPS
	)
	return f"""
<div class="se-wrap">
  <div class="se-head">
    <img class="se-logo" src="/assets/sanvidhi_epc/images/sanvidhi_epc_logo.svg" alt="">
    <div><div class="se-title">Sanvidhi EPC</div>
    <div class="se-tag">BOQ to final bill, site to digest, plot booking to possession</div></div>
  </div>
  {groups}
</div>
"""


TILE_CSS = """
.se-wrap{font-family:var(--font-stack, Inter, sans-serif);padding:4px 2px 8px}
.se-head{display:flex;gap:14px;align-items:center;margin-bottom:10px}
.se-logo{width:46px;height:46px}
.se-title{font-size:20px;font-weight:600;color:var(--heading-color,#1f272e)}
.se-tag{font-size:13px;color:var(--text-muted,#6c7680)}
.se-group{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--text-muted,#6c7680);margin:14px 0 8px}
.se-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:10px}
.se-tile{display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 8px 12px;border-radius:12px;
  border:1px solid var(--border-color,#ededed);background:var(--card-bg,#fff);text-decoration:none!important;
  color:var(--text-color,#1f272e);transition:box-shadow .15s,transform .15s}
.se-tile:hover{box-shadow:0 4px 14px rgba(0,0,0,.08);transform:translateY(-1px)}
.se-tile img,.se-ph{width:46px;height:46px;border-radius:12px}
.se-ph{background:var(--gray-200,#e2e6e9);display:block}
.se-label{font-size:13px;font-weight:600;text-align:center;line-height:1.2}
.se-sub{font-size:11px;color:var(--text-muted,#6c7680);text-align:center}
"""

# Links inside a Custom HTML Block sit in a shadow root; route them through
# the desk router so navigation stays a single-page transition.
TILE_JS = """
root_element.querySelectorAll('a.se-tile').forEach((a) => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    frappe.router.push_state(a.getAttribute('href'));
  });
});
"""

BLOCK_NAME = "Sanvidhi EPC Apps"


def sync_block():
	if frappe.db.exists("Custom HTML Block", BLOCK_NAME):
		doc = frappe.get_doc("Custom HTML Block", BLOCK_NAME)
	else:
		doc = frappe.new_doc("Custom HTML Block")
		doc.name = BLOCK_NAME
	doc.html, doc.style, doc.script, doc.private = tiles_html(), TILE_CSS, TILE_JS, 0
	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(set_name=BLOCK_NAME)
	else:
		doc.save()
