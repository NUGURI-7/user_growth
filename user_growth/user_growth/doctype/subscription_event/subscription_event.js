// Copyright (c) 2026, nuguri and contributors
// For license information, please see license.txt

const PLAN_MONTHLY_FEE = {
	Basic: 99,
	Professional: 299,
	Enterprise: 999,
};

frappe.ui.form.on("Subscription Event", {
	setup(frm) {
		// Only active, submitted subscriptions can be churned
		frm.set_query("subscription", () => ({
			filters: {
				event_type: "Subscribe",
				docstatus: 1,
				status: "Active",
			},
		}));
	},

	event_type(frm) {
		if (frm.doc.event_type === "Subscribe") {
			frm.set_value("subscription", null);
		}
	},

	plan(frm) {
		if (frm.doc.event_type === "Subscribe" && PLAN_MONTHLY_FEE[frm.doc.plan]) {
			frm.set_value("monthly_fee", PLAN_MONTHLY_FEE[frm.doc.plan]);
		}
	},
});
