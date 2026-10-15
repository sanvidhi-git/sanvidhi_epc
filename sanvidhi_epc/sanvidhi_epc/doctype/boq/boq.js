frappe.ui.form.on("BOQ", {
	setup(frm) {
		frm.set_query("project", () => ({ filters: { company: frm.doc.company, status: "Open" } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Contractor Work Order"), () =>
				frappe.new_doc("Contractor Work Order", { company: frm.doc.company, project: frm.doc.project, boq: frm.doc.name })
			, __("Create"));
			frm.add_custom_button(__("Client Measurement"), () =>
				frappe.new_doc("Measurement Book", {
					company: frm.doc.company, project: frm.doc.project, boq: frm.doc.name, mb_type: "Client",
				})
			, __("Create"));
			frm.add_custom_button(__("Client RA Bill"), () =>
				frappe.new_doc("Client RA Bill", { company: frm.doc.company, boq: frm.doc.name })
			, __("Create"));
		}
		if (frm.doc.docstatus === 1) {
			// standard ERPNext project management on top of the BOQ
			frm.add_custom_button(__("Tasks"), () =>
				frappe.set_route("List", "Task", { project: frm.doc.project })
			, __("View"));
			frm.add_custom_button(__("Gantt"), () =>
				frappe.set_route("List", "Task", "Gantt", { project: frm.doc.project })
			, __("View"));
			frm.add_custom_button(__("Project"), () => frappe.set_route("Form", "Project", frm.doc.project), __("View"));
			frm.add_custom_button(__("Refresh Progress"), () =>
				frappe.call({
					method: "sanvidhi_epc.sanvidhi_epc.doctype.boq.boq.refresh_progress",
					args: { boq: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				})
			, __("View"));
		}
		if (frm.doc.total_contract_value) {
			const pct = flt(frm.doc.planned_margin_percent, 1);
			let html = `<span class="indicator ${pct >= 15 ? "green" : "orange"}">${__("Planned margin")}: ${pct}%</span>
				&nbsp; ${__("Contract")}: <b>${format_currency(frm.doc.total_contract_value)}</b>
				&nbsp; ${__("Budgeted cost")}: <b>${format_currency(frm.doc.total_budgeted_cost)}</b>`;
			if (frm.doc.docstatus === 1 && frm.doc.actuals_updated_on) {
				const m = flt(frm.doc.margin_on_work_done_percent, 1);
				html += `<br><span class="indicator ${flt(frm.doc.margin_on_work_done) >= 0 ? "green" : "red"}">
					${__("Complete")}: ${flt(frm.doc.percent_complete, 1)}%</span>
					&nbsp; ${__("Work done")}: <b>${format_currency(frm.doc.value_of_work_done)}</b>
					&nbsp; ${__("Actual cost")}: <b>${format_currency(frm.doc.actual_cost)}</b>
					&nbsp; ${__("Margin on work done")}: <b>${format_currency(frm.doc.margin_on_work_done)} (${m}%)</b>`;
			}
			frm.dashboard.set_headline_alert(html);
		}
	},
});

frappe.ui.form.on("BOQ Item", {
	qty: (frm, cdt, cdn) => calc(frm, cdt, cdn),
	rate: (frm, cdt, cdn) => calc(frm, cdt, cdn),
	cost_rate: (frm, cdt, cdn) => calc(frm, cdt, cdn),
});

function calc(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	frappe.model.set_value(cdt, cdn, "cost_amount", flt(row.qty) * flt(row.cost_rate));
	const total = (frm.doc.items || []).reduce((s, r) => s + flt(r.amount), 0);
	const cost = (frm.doc.items || []).reduce((s, r) => s + flt(r.cost_amount), 0);
	frm.set_value("total_contract_value", total);
	frm.set_value("total_budgeted_cost", cost);
	frm.set_value("planned_margin", total - cost);
	frm.set_value("planned_margin_percent", total ? ((total - cost) / total) * 100 : 0);
}
