frappe.ui.form.on("Plot", {
	refresh(frm) {
		const colours = { Available: "green", Booked: "orange", Sold: "blue", Blocked: "red" };
		frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "gray");
		if (!frm.is_new() && frm.doc.status === "Available") {
			frm.add_custom_button(__("Book this Plot"), () =>
				frappe.new_doc("Plot Booking", { plot: frm.doc.name })
			);
		}
		if (frm.doc.plot_booking) {
			frm.add_custom_button(__("Current Booking"), () =>
				frappe.set_route("Form", "Plot Booking", frm.doc.plot_booking)
			);
		}
	},
	area_sqft: (frm) => frm.set_value("base_value", flt(frm.doc.area_sqft) * flt(frm.doc.rate_per_sqft)),
	rate_per_sqft: (frm) => frm.set_value("base_value", flt(frm.doc.area_sqft) * flt(frm.doc.rate_per_sqft)),
});
