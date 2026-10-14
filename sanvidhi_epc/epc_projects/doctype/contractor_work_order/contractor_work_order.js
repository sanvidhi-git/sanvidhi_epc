frappe.ui.form.on("Contractor Work Order", {
	setup(frm) {
		frm.set_query("boq", () => ({ filters: { docstatus: 1, status: "Active", project: frm.doc.project } }));
		frm.set_query("project", () => ({ filters: { company: frm.doc.company, status: "Open" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.boq) {
			frm.add_custom_button(__("Get Items from BOQ"), () => get_boq_items(frm));
		}
		if (frm.doc.docstatus === 1) {
			if (["Open", "Completed"].includes(frm.doc.status)) {
				frm.add_custom_button(__("Measurement Book"), () =>
					frappe.new_doc("Measurement Book", {
						company: frm.doc.company, project: frm.doc.project, boq: frm.doc.boq,
						mb_type: "Contractor", contractor_work_order: frm.doc.name,
					})
				, __("Create"));
				frm.add_custom_button(__("RA Bill"), () =>
					frappe.new_doc("Contractor RA Bill", { company: frm.doc.company, contractor_work_order: frm.doc.name })
				, __("Create"));
				frm.add_custom_button(__("Close"), () =>
					frappe.call("sanvidhi_epc.epc_projects.doctype.contractor_work_order.contractor_work_order.close_work_order",
						{ name: frm.doc.name }).then(() => frm.reload_doc())
				, __("Status"));
			} else if (frm.doc.status === "Closed") {
				frm.add_custom_button(__("Re-open"), () =>
					frappe.call("sanvidhi_epc.epc_projects.doctype.contractor_work_order.contractor_work_order.close_work_order",
						{ name: frm.doc.name, status: "Open" }).then(() => frm.reload_doc())
				, __("Status"));
			}
			const pending = flt(frm.doc.mobilisation_advance) - flt(frm.doc.advance_recovered);
			frm.dashboard.set_headline_alert(
				`${__("Order")}: <b>${format_currency(frm.doc.total_amount)}</b> &nbsp;
				${__("Measured")}: <b>${format_currency(frm.doc.measured_amount)}</b> &nbsp;
				${__("Billed")}: <b>${format_currency(frm.doc.billed_amount)}</b> &nbsp;
				${__("Advance to recover")}: <b>${format_currency(pending)}</b>`
			);
		}
	},
});

frappe.ui.form.on("Contractor Work Order Item", {
	qty: (frm, cdt, cdn) => calc(frm, cdt, cdn),
	rate: (frm, cdt, cdn) => calc(frm, cdt, cdn),
});

function calc(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	frm.set_value("total_amount", (frm.doc.items || []).reduce((s, r) => s + flt(r.amount), 0));
}

function get_boq_items(frm) {
	frappe.call({
		method: "sanvidhi_epc.epc_projects.doctype.boq.boq.get_boq_items",
		args: { boq: frm.doc.boq },
		callback(r) {
			const rows = (r.message || []).map((d) => ({
				label: `${d.boq_ref} · ${(d.description || "").slice(0, 60)} (${d.qty - d.contracted_qty} ${d.uom} open)`,
				value: d.name,
				checked: 0,
			}));
			const dlg = new frappe.ui.Dialog({
				title: __("Select BOQ lines to award"),
				fields: [{ fieldname: "rows", fieldtype: "MultiCheck", options: rows, columns: 1 }],
				primary_action_label: __("Add"),
				primary_action(values) {
					const picked = new Set(values.rows || []);
					const have = new Set((frm.doc.items || []).map((i) => i.boq_ref));
					(r.message || []).filter((d) => picked.has(d.name) && !have.has(d.boq_ref)).forEach((d) => {
						const row = frm.add_child("items", {
							boq_ref: d.boq_ref, boq_item: d.name, description: d.description, uom: d.uom,
							qty: Math.max(d.qty - d.contracted_qty, 0), rate: d.cost_rate || 0,
						});
						row.amount = flt(row.qty) * flt(row.rate);
					});
					frm.refresh_field("items");
					frm.set_value("total_amount", (frm.doc.items || []).reduce((s, x) => s + flt(x.amount), 0));
					dlg.hide();
				},
			});
			dlg.show();
		},
	});
}
