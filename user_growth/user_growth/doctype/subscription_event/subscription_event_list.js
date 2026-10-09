frappe.listview_settings["Subscription Event"] = {
	add_fields: ["event_type", "status"],

	formatters: {
		plan: (value) => __(value, null, "Subscription Event"),
		region: (value) => __(value, null, "Subscription Event"),
	},

	// Draft / Cancelled are handled by the framework; this covers submitted docs
	get_indicator(doc) {
		if (doc.event_type === "Churn") {
			return [__("Churn", null, "Subscription Event"), "red", "event_type,=,Churn"];
		}
		if (doc.status === "Churned") {
			return [__("Churned", null, "Subscription Event"), "gray", "status,=,Churned"];
		}
		return [__("Active", null, "Subscription Event"), "green", "status,=,Active"];
	},
};
