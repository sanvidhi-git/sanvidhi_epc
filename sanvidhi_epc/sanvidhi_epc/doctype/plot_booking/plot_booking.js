frappe.ui.form.on("Plot Booking", {
	setup(frm) {
		frm.set_query("plot", () => ({ filters: { status: "Available" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.agreed_value && !(frm.doc.payment_schedule || []).length) {
			frm.add_custom_button(__("Standard Schedule"), () => standard_schedule(frm));
		}
		if (frm.doc.docstatus === 1) {
			if (!frm.doc.sales_order) {
				frm.add_custom_button(__("Sales Order"), () =>
					frappe.call("sanvidhi_epc.sanvidhi_epc.doctype.plot_booking.plot_booking.make_sales_order",
						{ source_name: frm.doc.name }).then((r) => frappe.set_route("Form", "Sales Order", r.message))
				, __("Create"));
			}
			frm.add_custom_button(__("Demand Letter"), () =>
				frappe.new_doc("Demand Letter", { plot_booking: frm.doc.name, company: frm.doc.company })
			, __("Create"));
			frm.add_custom_button(__("Plot Handover"), () =>
				frappe.new_doc("Plot Handover", { plot_booking: frm.doc.name, company: frm.doc.company })
			, __("Create"));
			frm.add_custom_button(__("Refresh Dues"), () =>
				frm.call({ doc: frm.doc, method: "refresh_collections" }).then(() => frm.reload_doc())
			);
			frm.dashboard.set_headline_alert(
				`${__("Agreed")}: <b>${format_currency(frm.doc.agreed_value)}</b> &nbsp;
				${__("Received")}: <b>${format_currency(frm.doc.total_paid)}</b> &nbsp;
				<span class="indicator ${flt(frm.doc.outstanding) > 0 ? "orange" : "green"}">${__("Outstanding")}:
				${format_currency(frm.doc.outstanding)}</span>`
			);
		}
	},
	rate_per_sqft: (frm) => price(frm),
	discount_percent: (frm) => price(frm),
	broker_commission_percent: (frm) => price(frm),
	plot(frm) {
		if (frm.doc.plot) setTimeout(() => price(frm), 300);
	},
});

frappe.ui.form.on("Plot Payment Schedule", {
	percent(frm, cdt, cdn) {
		const r = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt((flt(frm.doc.agreed_value) * flt(r.percent)) / 100, 2));
	},
	amount: (frm) => total(frm),
	payment_schedule_remove: (frm) => total(frm),
});

function price(frm) {
	const base = flt(frm.doc.area_sqft) * flt(frm.doc.rate_per_sqft);
	const discount = flt((base * flt(frm.doc.discount_percent)) / 100, 2);
	frm.set_value("base_value", base);
	frm.set_value("discount_amount", discount);
	frm.set_value("agreed_value", base - discount);
	frm.set_value("broker_commission", flt(((base - discount) * flt(frm.doc.broker_commission_percent)) / 100, 2));
}

function total(frm) {
	frm.set_value("total_scheduled", (frm.doc.payment_schedule || []).reduce((s, r) => s + flt(r.amount), 0));
}

function standard_schedule(frm) {
	// a common plotted-development plan; edit freely before submitting
	const plan = [
		[__("Booking"), 10, 0],
		[__("Agreement"), 20, 30],
		[__("Road and drainage complete"), 30, 120],
		[__("Registration"), 40, 240],
	];
	plan.forEach(([milestone, pct, days]) =>
		frm.add_child("payment_schedule", {
			milestone, percent: pct,
			amount: flt((flt(frm.doc.agreed_value) * pct) / 100, 2),
			due_date: frappe.datetime.add_days(frm.doc.booking_date || frappe.datetime.get_today(), days),
		})
	);
	frm.refresh_field("payment_schedule");
	total(frm);
}
