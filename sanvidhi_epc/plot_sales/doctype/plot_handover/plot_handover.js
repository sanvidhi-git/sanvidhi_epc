frappe.ui.form.on("Plot Handover", {
	setup(frm) {
		frm.set_query("plot_booking", () => ({ filters: { docstatus: 1, status: "Booked" } }));
	},
	refresh(frm) {
		const dues = flt(frm.doc.dues_outstanding);
		if (frm.doc.plot_booking) {
			frm.dashboard.set_headline_alert(
				`<span class="indicator ${dues > 0.5 ? "red" : "green"}">${dues > 0.5
					? __("Dues outstanding: {0}", [format_currency(dues)])
					: __("No dues")}</span>`
			);
		}
	},
});
