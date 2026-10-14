frappe.ui.form.on("Certification", {
	setup(frm) {
		frm.set_query("client_ra_bill", () => ({ filters: { docstatus: 1, certification: ["is", "not set"] } }));
	},
	certified_amount(frm) {
		const diff = flt(frm.doc.submitted_amount) - flt(frm.doc.certified_amount);
		frm.set_value("difference", diff);
		frm.set_value("difference_percent", frm.doc.submitted_amount ? (diff / frm.doc.submitted_amount) * 100 : 0);
		frm.toggle_reqd("reason_for_difference", Math.abs(diff) > 0.5);
	},
	refresh(frm) {
		frm.toggle_reqd("reason_for_difference", Math.abs(flt(frm.doc.difference)) > 0.5);
	},
});
