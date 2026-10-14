frappe.ui.form.on("Daily Progress Report", {
	setup(frm) {
		frm.set_query("project", () => ({ filters: { company: frm.doc.company, status: "Open" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.project && !(frm.doc.work_done || []).length) {
			frm.add_custom_button(__("Copy Yesterday's Labour"), () => {
				frappe.db.get_list("Daily Progress Report", {
					filters: { project: frm.doc.project, docstatus: 1 },
					fields: ["name"], order_by: "report_date desc", limit: 1,
				}).then((r) => {
					if (!r.length) return frappe.msgprint(__("No earlier report for this project"));
					frappe.db.get_doc("Daily Progress Report", r[0].name).then((d) => {
						(d.labour || []).forEach((l) =>
							frm.add_child("labour", { category: l.category, supplier: l.supplier, count: l.count, hours: l.hours }));
						frm.refresh_field("labour");
						set_total(frm);
					});
				});
			});
		}
	},
});

frappe.ui.form.on("DPR Labour", {
	count: (frm) => set_total(frm),
	labour_remove: (frm) => set_total(frm),
});

function set_total(frm) {
	frm.set_value("total_labour", (frm.doc.labour || []).reduce((s, r) => s + cint(r.count), 0));
}
