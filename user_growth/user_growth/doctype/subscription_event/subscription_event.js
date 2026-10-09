// Copyright (c) 2026, nuguri and contributors
// For license information, please see license.txt

const PLAN_MONTHLY_FEE = {
	Basic: 99,
	Professional: 299,
	Enterprise: 999,
};

// Show select values in this doctype's translation context. Frappe's read-only
// Select formatter calls __(value) without context, so "Basic" would read "基础".
const translate_in_context = (value) => (value ? __(value, null, "Subscription Event") : "");

frappe.ui.form.on("Subscription Event", {
	setup(frm) {
		frm.meta.fields
			.filter((df) => df.fieldtype === "Select")
			.forEach((df) => (df.formatter = translate_in_context));

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
