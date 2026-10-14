frappe.listview_settings["Plot"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colours = { Available: "green", Booked: "orange", Sold: "blue", Blocked: "red" };
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
