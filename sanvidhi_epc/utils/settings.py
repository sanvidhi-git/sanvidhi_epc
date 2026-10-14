import frappe
from frappe import _

SETTINGS = "Sanvidhi EPC Settings"


def get_settings():
	return frappe.get_cached_doc(SETTINGS)


def require(fieldname):
	"""Value of a settings field, or a clear error naming the field to fill."""
	value = get_settings().get(fieldname)
	if not value:
		label = frappe.get_meta(SETTINGS).get_label(fieldname)
		frappe.throw(_("Set {0} in {1} first").format(frappe.bold(_(label)), frappe.bold(_(SETTINGS))))
	return value
