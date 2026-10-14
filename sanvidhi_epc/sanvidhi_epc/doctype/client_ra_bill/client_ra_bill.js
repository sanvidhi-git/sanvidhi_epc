frappe.ui.form.on("Client RA Bill", {
	setup(frm) {
		frm.set_query("boq", () => ({ filters: { docstatus: 1, status: "Active" } }));
		frm.set_query("measurement_book", "measurement_books", () => ({
			filters: { docstatus: 1, mb_type: "Client", billing_status: "Not Billed", boq: frm.doc.boq },
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.boq) {
			frm.add_custom_button(__("Get Measurements"), () =>
				frm.call({ doc: frm.doc, method: "get_measurements" }).then(() => frm.refresh_fields())
			);
		}
		if (frm.doc.docstatus === 1) {
			if (!frm.doc.certification) {
				frm.add_custom_button(__("Certification"), () =>
					frappe.new_doc("Certification", { client_ra_bill: frm.doc.name })
				, __("Create"));
			}
			if (!frm.doc.sales_invoice) {
				frm.add_custom_button(__("Sales Invoice"), () =>
					frappe.call("sanvidhi_epc.sanvidhi_epc.doctype.client_ra_bill.client_ra_bill.make_sales_invoice",
						{ source_name: frm.doc.name }).then((r) => frappe.set_route("Form", "Sales Invoice", r.message))
				, __("Create"));
			}
		}
		let msg = `${__("This bill")}: <b>${format_currency(frm.doc.current_value)}</b>`;
		if (frm.doc.certified_amount) {
			const gap = flt(frm.doc.current_value) - flt(frm.doc.certified_amount);
			msg += ` &nbsp; ${__("Certified")}: <b>${format_currency(frm.doc.certified_amount)}</b>
				&nbsp; <span class="indicator ${gap > 0 ? "orange" : "green"}">${__("Short-certified")}: ${format_currency(gap)}</span>`;
		}
		frm.dashboard.set_headline_alert(msg);
	},
	boq(frm) {
		if (frm.doc.boq && frm.is_new()) {
			frm.call({ doc: frm.doc, method: "get_measurements" }).then(() => frm.refresh_fields());
		}
	},
});
