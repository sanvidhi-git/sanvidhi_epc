app_name = "sanvidhi_epc"
app_title = "Sanvidhi EPC"
app_publisher = "Sanvidhi Tech Pvt. Ltd."
app_description = "Sanvidhi EPC - BOQ, contractor and client RA billing, measurement, site reporting and plot sales on ERPNext"
app_email = "info@sanvidhi.in"
app_license = "gpl-3.0"
app_logo_url = "/assets/sanvidhi_epc/images/sanvidhi_epc_logo.svg"
app_home = "/desk/sanvidhi-epc"
required_apps = ["erpnext"]

# ---------------------------------------------------------------- assets
app_include_css = "/assets/sanvidhi_epc/css/sanvidhi_epc.css"

# ---------------------------------------------------------------- apps screen
# frappe/apps.py::get_apps() only lists apps that declare this hook.
add_to_apps_screen = [
	{
		"name": "sanvidhi_epc",
		"logo": "/assets/sanvidhi_epc/images/sanvidhi_epc_logo.svg",
		"title": "Sanvidhi EPC",
		"route": "/desk/sanvidhi-epc",
		"has_permission": "sanvidhi_epc.utils.permissions.has_app_permission",
	}
]

# ---------------------------------------------------------------- install / migrate
# Roles are (re)created idempotently on every migrate so a fresh site and an upgraded
# site end in the same state.
after_install = "sanvidhi_epc.setup.install.after_install"
after_migrate = "sanvidhi_epc.setup.install.after_migrate"

# ---------------------------------------------------------------- standard doctypes
doc_events = {
	# workflow 8: optional rule - no new material request until yesterday's DPR is filed
	"Material Request": {"validate": "sanvidhi_epc.utils.site.validate_material_request"},
	# workflow 7: a receipt against a plot's sales order refreshes the booking's dues
	"Payment Entry": {
		"on_submit": "sanvidhi_epc.utils.collections.on_payment_entry",
		"on_cancel": "sanvidhi_epc.utils.collections.on_payment_entry",
	},
	"Sales Invoice": {
		"on_submit": "sanvidhi_epc.utils.collections.on_sales_invoice",
		"on_cancel": "sanvidhi_epc.utils.collections.on_sales_invoice",
	},
	# project cost -> the BOQ's progress and margin to date (value of work done vs actual cost)
	"Stock Entry": {
		"on_submit": "sanvidhi_epc.utils.planning.on_cost_document",
		"on_cancel": "sanvidhi_epc.utils.planning.on_cost_document",
	},
	"Timesheet": {
		"on_submit": "sanvidhi_epc.utils.planning.on_cost_document",
		"on_cancel": "sanvidhi_epc.utils.planning.on_cost_document",
	},
	"Purchase Invoice": {
		"on_submit": "sanvidhi_epc.utils.planning.on_cost_document",
		"on_cancel": "sanvidhi_epc.utils.planning.on_cost_document",
	},
}

# ---------------------------------------------------------------- scheduler
scheduler_events = {
	"daily": [
		# workflow 7: dues refreshed, overdue instalments flagged, demand letters drafted ahead of due date
		"sanvidhi_epc.tasks.demand.daily",
		# progress and margin on every active BOQ
		"sanvidhi_epc.utils.planning.daily",
	],
	"cron": {
		# workflow 8: evening digest of every open site's DPR (site time zone)
		"0 19 * * *": ["sanvidhi_epc.tasks.digest.scheduled"],
	},
}
