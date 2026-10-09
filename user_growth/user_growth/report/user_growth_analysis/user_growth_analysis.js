// Copyright (c) 2026, nuguri and contributors
// For license information, please see license.txt

// Option labels share translations with the Subscription Event form
const options = (values) => [
	{ value: "", label: "" },
	...values.map((value) => ({ value, label: __(value, null, "Subscription Event") })),
];

frappe.query_reports["User Growth Analysis"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			// Last 12 complete months; the current month is still in progress
			default: frappe.datetime.add_months(frappe.datetime.month_start(), -12),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.month_start(), -1),
			reqd: 1,
		},
		{
			fieldname: "plan",
			label: __("Plan"),
			fieldtype: "Select",
			options: options(["Basic", "Professional", "Enterprise"]),
		},
		{
			fieldname: "channel",
			label: __("Channel"),
			fieldtype: "Select",
			options: options(["Website", "Direct Sales", "Partner", "Referral"]),
		},
		{
			fieldname: "region",
			label: __("Region"),
			fieldtype: "Select",
			options: options(["North China", "East China", "South China", "Central China", "West China"]),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		const signed = { net_customers: data.net_customers, net_mrr: data.net_mrr };
		if (column.fieldname in signed && signed[column.fieldname] !== 0) {
			const color = signed[column.fieldname] > 0 ? "var(--green-600)" : "var(--red-600)";
			value = `<span style="color: ${color}">${value}</span>`;
		}
		return value;
	},
};
