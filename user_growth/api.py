import frappe
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, today

from user_growth.user_growth.report.user_growth_analysis.user_growth_analysis import base_query, get_rows

DIMENSIONS = ("plan", "channel", "region")


@frappe.whitelist()
def get_dashboard_data(months=12, plan=None, channel=None, region=None):
	"""Everything the User Growth Dashboard page needs, in one call.

	months: size of the trend window including the current month; 0 = all history.
	Each distribution ignores its own dimension filter, so the selected item
	stays highlighted among its siblings (cross-filtering).
	"""
	frappe.has_permission("Subscription Event", "read", throw=True)

	filters = frappe._dict(plan=plan or None, channel=channel or None, region=region or None)
	end = getdate(today())
	month_start = get_first_day(end)
	months = cint(months)
	from_date = add_months(month_start, -(months - 1)) if months > 0 else _first_month(month_start)
	# At least two months so the KPIs can compare with last month
	from_date = min(getdate(from_date), getdate(add_months(month_start, -1)))

	trend = get_rows(filters, from_date, end)
	return {
		"as_of": frappe.utils.now_datetime(),
		"from_date": from_date,
		"trend": trend,
		"kpis": _kpis(filters, trend, end),
		"plans": _group(_without(filters, "plan"), "plan", active_only=True),
		"regions": _group(_without(filters, "region"), "region", active_only=True),
		"channels": _group(_without(filters, "channel"), "channel", event_type="Subscribe", from_date=from_date),
		"churn_reasons": _group(filters, "churn_reason", event_type="Churn", from_date=from_date),
		"recent": _recent(filters),
	}


def _kpis(filters, trend, end):
	current, previous = trend[-1], trend[-2]
	# Month-to-date vs the same days of last month
	prev_start = get_first_day(add_months(end, -1))
	prev_end = min(add_days(prev_start, end.day - 1), get_last_day(prev_start))
	return {
		"active": {"value": current["active_customers"], "previous": previous["active_customers"]},
		"mrr": {"value": current["mrr"], "previous": previous["mrr"]},
		"new": {
			"value": current["new_customers"],
			"previous": _count(filters, "Subscribe", prev_start, prev_end),
		},
		"churned": {
			"value": current["churned_customers"],
			"previous": _count(filters, "Churn", prev_start, prev_end),
		},
		"month_start": get_first_day(end),
	}


def _count(filters, event_type, from_date, to_date):
	se, query = base_query(filters)
	return (
		query.select(Count("*"))
		.where((se.event_type == event_type) & se.event_date[from_date:to_date])
		.run()[0][0]
	)


def _group(filters, field, active_only=False, event_type=None, from_date=None):
	se, query = base_query(filters)
	if active_only:
		query = query.where((se.event_type == "Subscribe") & (se.status == "Active"))
	if event_type:
		query = query.where(se.event_type == event_type)
	if from_date:
		query = query.where(se.event_date >= from_date)
	rows = (
		query.select(se[field].as_("label"), Count("*").as_("count"), Sum(se.monthly_fee).as_("mrr"))
		.groupby(se[field])
		.orderby(Count("*"), order=frappe.qb.desc)
		.run(as_dict=True)
	)
	return [{"label": r.label, "count": r.count, "mrr": flt(r.mrr)} for r in rows if r.label]


def _recent(filters, limit=10):
	se, query = base_query(filters)
	return (
		query.select(
			se.name, se.event_type, se.event_date, se.customer_name, se.plan, se.monthly_fee, se.churn_reason
		)
		.orderby(se.event_date, order=frappe.qb.desc)
		.orderby(se.creation, order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)


def _without(filters, field):
	return frappe._dict({k: v for k, v in filters.items() if k != field})


def _first_month(fallback):
	first = frappe.db.get_value("Subscription Event", {"docstatus": 1}, "min(event_date)")
	return get_first_day(first) if first else fallback
