# Copyright (c) 2026, nuguri and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Case, DocType
from frappe.query_builder.functions import Count, DateFormat, Sum
from frappe.utils import add_months, flt, fmt_money, get_first_day, getdate

DIMENSIONS = ("plan", "channel", "region")
# Translation context for words Frappe already translates differently (e.g. "New")
CTX = "Subscription Event"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = get_first_day(filters.from_date)
	to_date = getdate(filters.to_date)
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))

	rows = get_rows(filters, from_date, to_date)
	return get_columns(), rows, None, get_chart(rows), get_summary(rows)


def get_rows(filters, from_date, to_date):
	active, mrr = get_opening(filters, from_date)
	movements = get_movements(filters, from_date, to_date)

	rows = []
	month = from_date
	while month <= to_date:
		key = month.strftime("%Y-%m")
		m = movements.get(key, {})
		new, churned = m.get("Subscribe", (0, 0)), m.get("Churn", (0, 0))
		opening_active = active
		active += new[0] - churned[0]
		mrr += new[1] - churned[1]
		rows.append(
			{
				"month": key,
				"new_customers": new[0],
				"churned_customers": churned[0],
				"net_customers": new[0] - churned[0],
				"opening_customers": opening_active,
				"active_customers": active,
				"churn_rate": churned[0] * 100 / opening_active if opening_active else None,
				"new_mrr": new[1],
				"churned_mrr": churned[1],
				"net_mrr": new[1] - churned[1],
				"mrr": mrr,
			}
		)
		month = add_months(month, 1)
	return rows


def base_query(filters):
	se = DocType("Subscription Event")
	query = frappe.qb.from_(se).where(se.docstatus == 1)
	for field in DIMENSIONS:
		if filters.get(field):
			query = query.where(se[field] == filters.get(field))
	return se, query


def get_opening(filters, from_date):
	"""Active customers and MRR right before from_date."""
	se, query = base_query(filters)
	sign = Case().when(se.event_type == "Subscribe", 1).else_(-1)
	result = (
		query.select(Sum(sign).as_("active"), Sum(sign * se.monthly_fee).as_("mrr"))
		.where(se.event_date < from_date)
		.run(as_dict=True)
	)[0]
	return int(result.active or 0), flt(result.mrr)


def get_movements(filters, from_date, to_date):
	"""{"YYYY-MM": {event_type: (count, mrr)}} within the range."""
	se, query = base_query(filters)
	month = DateFormat(se.event_date, "%Y-%m")
	result = (
		query.select(
			month.as_("month"),
			se.event_type,
			Count("*").as_("count"),
			Sum(se.monthly_fee).as_("mrr"),
		)
		.where(se.event_date[from_date:to_date])
		.groupby(month, se.event_type)
		.run(as_dict=True)
	)
	movements = {}
	for r in result:
		movements.setdefault(r.month, {})[r.event_type] = (r.count, flt(r.mrr))
	return movements


def get_columns():
	return [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 100},
		{"fieldname": "new_customers", "label": _("New", context=CTX), "fieldtype": "Int", "width": 90},
		{"fieldname": "churned_customers", "label": _("Churned"), "fieldtype": "Int", "width": 90},
		{"fieldname": "net_customers", "label": _("Net Growth"), "fieldtype": "Int", "width": 110},
		{"fieldname": "opening_customers", "label": _("Opening Active"), "fieldtype": "Int", "width": 120},
		{"fieldname": "active_customers", "label": _("Closing Active"), "fieldtype": "Int", "width": 120},
		{"fieldname": "churn_rate", "label": _("Churn Rate"), "fieldtype": "Percent", "precision": 1, "width": 110},
		{"fieldname": "new_mrr", "label": _("New MRR"), "fieldtype": "Currency", "precision": 0, "width": 120},
		{"fieldname": "churned_mrr", "label": _("Churned MRR"), "fieldtype": "Currency", "precision": 0, "width": 120},
		{"fieldname": "net_mrr", "label": _("Net MRR"), "fieldtype": "Currency", "precision": 0, "width": 120},
		{"fieldname": "mrr", "label": _("Closing MRR"), "fieldtype": "Currency", "precision": 0, "width": 130},
	]


def get_chart(rows):
	return {
		"data": {
			"labels": [r["month"] for r in rows],
			"datasets": [
				{"name": _("New", context=CTX), "values": [r["new_customers"] for r in rows]},
				{"name": _("Churned"), "values": [r["churned_customers"] for r in rows]},
			],
		},
		"type": "bar",
		"colors": ["#5bb98c", "#e8787c"],
		"barOptions": {"spaceRatio": 0.5},
	}


def get_summary(rows):
	if not rows:
		return []
	new = sum(r["new_customers"] for r in rows)
	churned = sum(r["churned_customers"] for r in rows)
	exposure = sum(r["opening_customers"] for r in rows)
	churn_rate = churned * 100 / exposure if exposure else 0
	last = rows[-1]
	currency = frappe.db.get_default("currency")
	return [
		{"label": _("New Customers"), "value": new, "datatype": "Int", "indicator": "Green"},
		{"label": _("Churned Customers"), "value": churned, "datatype": "Int", "indicator": "Red"},
		{"label": _("Net Growth"), "value": new - churned, "datatype": "Int"},
		{"label": _("Active Customers"), "value": last["active_customers"], "datatype": "Int"},
		{"label": _("Avg Monthly Churn Rate"), "value": f"{churn_rate:.1f}%", "datatype": "Data"},
		{
			"label": _("Closing MRR"),
			"value": fmt_money(last["mrr"], precision=0, currency=currency),
			"datatype": "Data",
		},
	]
