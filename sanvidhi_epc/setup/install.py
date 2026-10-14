"""Idempotent setup: runs after install and after every migrate."""

import frappe

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
	settings = frappe.get_single("Sanvidhi EPC Settings")
	if not settings.company:
		company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if company:
			settings.company = company
			settings.flags.ignore_mandatory = True
			settings.save(ignore_permissions=True)
	frappe.db.commit()
