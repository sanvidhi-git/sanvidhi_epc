frappe.ui.form.on("Daily Digest", {
	refresh(frm) {
		frm.get_field("preview").$wrapper.html(frm.doc.summary_html || `<p class="text-muted">${__("Not built yet")}</p>`);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Rebuild"), () =>
				frm.call({ doc: frm.doc, method: "rebuild" }).then(() => frm.reload_doc()));
			frm.add_custom_button(__("Send Now"), () =>
				frm.call({ doc: frm.doc, method: "send_now" }).then(() => frm.reload_doc()));
		}
	},
});
