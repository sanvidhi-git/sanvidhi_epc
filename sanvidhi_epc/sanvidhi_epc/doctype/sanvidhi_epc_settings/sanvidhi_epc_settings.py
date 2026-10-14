# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SanvidhiEPCSettings(Document):
	def validate(self):
		for field in ("retention_payable_account", "contractor_advance_account", "retention_receivable_account"):
			account = self.get(field)
			if not account:
				continue
			acc = frappe.db.get_value("Account", account, ["company", "is_group"], as_dict=True)
			if acc and acc.company != self.company:
				frappe.throw(_("Account {0} does not belong to {1}").format(account, self.company))
			if acc and acc.is_group:
				frappe.throw(_("Account {0} is a group account").format(account))
		for field in ("contractor_service_item", "client_billing_item", "plot_sale_item"):
			item = self.get(field)
			if item and frappe.db.get_value("Item", item, "is_stock_item"):
				frappe.throw(_("{0} must be a non-stock item").format(item))
