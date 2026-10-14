const CRA = "sanvidhi_epc.epc_projects.doctype.contractor_ra_bill.contractor_ra_bill";

frappe.ui.form.on("Contractor RA Bill", {
	setup(frm) {
		frm.set_query("contractor_work_order", () => ({ filters: { docstatus: 1, status: ["in", ["Open", "Completed"]] } }));
		frm.set_query("measurement_book", "measurement_books", () => ({
			filters: {
				docstatus: 1, mb_type: "Contractor", billing_status: "Not Billed",
				contractor_work_order: frm.doc.contractor_work_order,
			},
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.contractor_work_order) {
			frm.add_custom_button(__("Get Measurements"), () =>
				frm.call({ doc: frm.doc, method: "get_measurements" }).then(() => frm.refresh_fields())
			);
		}
		if (frm.doc.docstatus === 1) {
			if (!frm.doc.purchase_invoice) {
				frm.add_custom_button(__("Purchase Invoice"), () =>
					frappe.call(`${CRA}.make_purchase_invoice`, { source_name: frm.doc.name }).then((r) =>
						frappe.set_route("Form", "Purchase Invoice", r.message))
				, __("Create"));
			}
			if (!frm.doc.journal_entry && (frm.doc.retention_amount || frm.doc.advance_recovery_amount)) {
				frm.add_custom_button(__("Retention / Advance Journal"), () =>
					frappe.call(`${CRA}.make_deduction_journal`, { source_name: frm.doc.name }).then((r) =>
						frappe.set_route("Form", "Journal Entry", r.message))
				, __("Create"));
			}
		}
		frm.dashboard.set_headline_alert(
			`${__("This bill")}: <b>${format_currency(frm.doc.current_value)}</b> &nbsp;
			${__("Net payable")}: <b>${format_currency(frm.doc.net_payable)}</b>`
		);
	},
	contractor_work_order(frm) {
		if (frm.doc.contractor_work_order && frm.is_new()) {
			frm.call({ doc: frm.doc, method: "get_measurements" }).then(() => frm.refresh_fields());
		}
	},
	retention_percent: (frm) => frm.dirty(),
	tds_percent: (frm) => frm.dirty(),
});
