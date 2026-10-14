frappe.ui.form.on("Demand Letter", {
	setup(frm) {
		frm.set_query("plot_booking", () => ({ filters: { docstatus: 1, status: "Booked" } }));
	},
	plot_booking(frm) {
		if (!frm.doc.plot_booking) return;
		frappe.db.get_doc("Plot Booking", frm.doc.plot_booking).then((b) => {
			const open = (b.payment_schedule || []).filter((r) => !r.demand_letter && r.status !== "Paid");
			if (!open.length) return frappe.msgprint(__("Every instalment of this booking is already demanded or paid"));
			const pick = (row) => {
				frm.set_value("milestone", row.milestone);
				frm.set_value("schedule_row", row.name);
				frm.set_value("due_date", row.due_date);
				frm.set_value("instalment_amount", flt(row.amount) - flt(row.paid_amount));
			};
			if (open.length === 1) return pick(open[0]);
			frappe.prompt(
				{
					fieldname: "milestone", fieldtype: "Select", label: __("Instalment"), reqd: 1,
					options: open.map((r) => r.milestone),
				},
				(v) => pick(open.find((r) => r.milestone === v.milestone)),
				__("Which instalment?")
			);
		});
	},
});
