frappe.ui.form.on("Measurement Book", {
	setup(frm) {
		frm.set_query("contractor_work_order", () => ({
			filters: { docstatus: 1, status: ["in", ["Open", "Completed"]], project: frm.doc.project || undefined },
		}));
		frm.set_query("boq", () => ({ filters: { docstatus: 1, status: "Active" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Lines"), () => get_lines(frm));
		}
		if (frm.doc.docstatus === 1 && frm.doc.billing_status === "Not Billed") {
			const target = frm.doc.mb_type === "Contractor" ? "Contractor RA Bill" : "Client RA Bill";
			frm.add_custom_button(__(target), () =>
				frappe.new_doc(target, frm.doc.mb_type === "Contractor"
					? { company: frm.doc.company, contractor_work_order: frm.doc.contractor_work_order }
					: { company: frm.doc.company, boq: frm.doc.boq })
			, __("Create"));
		}
	},
	contractor_work_order(frm) {
		if (!frm.doc.contractor_work_order) return;
		frappe.db.get_value("Contractor Work Order", frm.doc.contractor_work_order, ["boq", "project"]).then((r) => {
			frm.set_value("boq", r.message.boq);
			frm.set_value("project", r.message.project);
		});
	},
});

frappe.ui.form.on("Measurement Book Item", {
	nos: (frm, cdt, cdn) => calc(cdt, cdn),
	length: (frm, cdt, cdn) => calc(cdt, cdn),
	breadth: (frm, cdt, cdn) => calc(cdt, cdn),
	depth: (frm, cdt, cdn) => calc(cdt, cdn),
});

function calc(cdt, cdn) {
	const r = locals[cdt][cdn];
	const dims = [flt(r.length), flt(r.breadth), flt(r.depth)];
	if (!dims.some(Boolean)) return;
	let q = flt(r.nos) || 1;
	dims.forEach((d) => (q *= d || 1));
	frappe.model.set_value(cdt, cdn, "qty", q);
}

function get_lines(frm) {
	const contractor = frm.doc.mb_type === "Contractor";
	if (contractor && !frm.doc.contractor_work_order) return frappe.msgprint(__("Select the work order first"));
	if (!contractor && !frm.doc.boq) return frappe.msgprint(__("Select the BOQ first"));
	frappe.call({
		method: contractor
			? "sanvidhi_epc.sanvidhi_epc.doctype.contractor_work_order.contractor_work_order.get_work_order_items"
			: "sanvidhi_epc.sanvidhi_epc.doctype.boq.boq.get_boq_items",
		args: contractor ? { work_order: frm.doc.contractor_work_order } : { boq: frm.doc.boq },
		callback(r) {
			const have = new Set((frm.doc.items || []).map((i) => i.boq_ref));
			(r.message || []).filter((d) => !have.has(d.boq_ref)).forEach((d) => {
				frm.add_child("items", { boq_ref: d.boq_ref, description: d.description, uom: d.uom, nos: 1 });
			});
			frm.refresh_field("items");
		},
	});
}
