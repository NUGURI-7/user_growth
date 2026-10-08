frappe.listview_settings["Subscription Event"] = {
	add_fields: ["event_type", "status"],

	// Draft / Cancelled are handled by the framework; this covers submitted docs
	get_indicator(doc) {
		if (doc.event_type === "Churn") {
			return [__("Churn"), "red", "event_type,=,Churn"];
		}
		if (doc.status === "Churned") {
			return [__("Churned"), "gray", "status,=,Churned"];
		}
		return [__("Active"), "green", "status,=,Active"];
	},
};
