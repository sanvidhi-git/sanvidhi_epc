import frappe

from sanvidhi_epc.setup.install import ROLES

MD_ROLES = {"EPC MD", "System Manager"}
APPROVER_ROLES = {"EPC MD", "EPC Project Manager", "System Manager"}


def has_app_permission():
	"""Who sees the Sanvidhi EPC tile on the /apps screen."""
	if frappe.session.user == "Administrator":
		return True
	return bool((set(ROLES) | {"System Manager"}) & set(frappe.get_roles()))


def user_has_any(roles):
	return frappe.session.user == "Administrator" or bool(set(roles) & set(frappe.get_roles()))
