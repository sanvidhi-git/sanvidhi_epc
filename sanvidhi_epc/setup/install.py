"""Idempotent setup: runs after install and after every migrate."""

import frappe

from sanvidhi_epc.setup.module_tiles import sync_block

ROLES = [
	"EPC MD",
	"EPC Project Manager",
	"EPC Site Engineer",
	"EPC Billing Engineer",
	"EPC Accounts User",
	"Plot Sales User",
]


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
	# the workspace's icon grid of apps (a Custom HTML Block is not a fixture, so it is rebuilt here)
	sync_block()
	# project management: Task / Timesheet fields, site labour activity types, "EPC Site" project template
	from sanvidhi_epc.utils.planning import setup_masters

	setup_masters()
	settings = frappe.get_single("Sanvidhi EPC Settings")
	if not settings.company:
		company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if company:
			settings.company = company
			settings.flags.ignore_mandatory = True
			settings.save(ignore_permissions=True)
	frappe.db.commit()
