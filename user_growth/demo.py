"""Demo data for Subscription Event.

Generates ~21 months of subscribe / churn events ending today, so the report
and dashboard always have a populated "current month". A fixed random seed
keeps the shape of the data identical on every install.

Every record goes through insert() + submit(), so the same validation as
manual entry applies.

Regenerate from the console:
	bench --site <site> execute user_growth.demo.make_demo_data --kwargs "{'force': True}"
"""

import calendar
import random
from datetime import date

import frappe
from frappe.utils import add_months, get_first_day, getdate, today

DOCTYPE = "Subscription Event"
SEED = 20260101
HISTORY_MONTHS = 20  # full months before the current one

PLAN_FEES = {
	"Basic": [99],
	"Professional": [299],
	"Enterprise": [999, 1499, 1999],
}
PLAN_WEIGHTS = {"Basic": 55, "Professional": 33, "Enterprise": 12}
# Monthly churn probability per active customer
PLAN_CHURN_RATE = {"Basic": 0.06, "Professional": 0.035, "Enterprise": 0.015}

CHANNEL_WEIGHTS = {"Website": 35, "Direct Sales": 25, "Partner": 20, "Referral": 20}
REGION_WEIGHTS = {
	"East China": 35,
	"South China": 25,
	"North China": 20,
	"Central China": 12,
	"West China": 8,
}
CHURN_REASON_WEIGHTS = {
	"Basic": {"Price": 40, "Competitor": 20, "Missing Features": 20, "Service Experience": 10, "Business Change": 10},
	"Professional": {"Price": 20, "Competitor": 30, "Missing Features": 25, "Service Experience": 15, "Business Change": 10},
	"Enterprise": {"Price": 10, "Competitor": 20, "Missing Features": 20, "Service Experience": 15, "Business Change": 35},
}

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安", "厦门", "长沙", "重庆", "天津", "合肥"]
BRANDS = [
	"云启", "数联", "智汇", "星辰", "博远", "恒信", "瑞达", "嘉禾", "领航", "新元",
	"华盛", "启明", "睿思", "鼎峰", "益通", "青藤", "蓝海", "极光", "天衡", "卓越",
	"宏图", "汇智", "长风", "锦程", "致远", "明德", "优创", "联科", "安捷", "合众",
]
INDUSTRIES = ["科技", "信息技术", "网络科技", "软件", "数据服务", "电子商务", "咨询", "物流", "教育科技", "医疗科技"]


def make_demo_data(force=False):
	if frappe.db.count(DOCTYPE) and not force:
		return
	if force:
		frappe.db.delete(DOCTYPE)

	rng = random.Random(SEED)
	names = _name_pool(rng)
	end = getdate(today())
	first_month = get_first_day(add_months(end, -HISTORY_MONTHS))

	active = []  # [(doc name, plan)] of active subscriptions, oldest first
	for i in range(HISTORY_MONTHS + 1):
		month_start = getdate(add_months(first_month, i))
		last_day = end.day if i == HISTORY_MONTHS else calendar.monthrange(month_start.year, month_start.month)[1]

		events = []
		# Pro-rate a partial current month
		month_ratio = last_day / calendar.monthrange(month_start.year, month_start.month)[1]
		# Churn: only customers who subscribed before this month are eligible
		for name, plan in list(active):
			if rng.random() < PLAN_CHURN_RATE[plan] * month_ratio:
				events.append(("Churn", _day(rng, month_start, last_day), (name, plan)))
		for _ in range(_new_count(rng, i, month_start, month_ratio)):
			events.append(("Subscribe", _day(rng, month_start, last_day), None))

		# Chronological order; on the same day, subscribe before churn
		events.sort(key=lambda e: (e[1], e[0] != "Subscribe"))
		for event_type, event_date, target in events:
			if event_type == "Subscribe":
				plan = _pick(rng, PLAN_WEIGHTS)
				doc = _create(
					event_type="Subscribe",
					event_date=event_date,
					customer_name=names.pop(),
					plan=plan,
					monthly_fee=rng.choice(PLAN_FEES[plan]),
					channel=_pick(rng, CHANNEL_WEIGHTS),
					region=_pick(rng, REGION_WEIGHTS),
				)
				active.append((doc.name, plan))
			else:
				name, plan = target
				_create(
					event_type="Churn",
					event_date=event_date,
					subscription=name,
					churn_reason=_pick(rng, CHURN_REASON_WEIGHTS[plan]),
				)
				active.remove(target)


def _new_count(rng, month_index, month_start, month_ratio):
	# Steady growth from ~20 to ~45 per month, dip around Chinese New Year
	base = 20 + month_index * 1.25
	if month_start.month == 2:
		base *= 0.7
	return round(base * rng.uniform(0.85, 1.15) * month_ratio)


def _create(**fields):
	doc = frappe.get_doc({"doctype": DOCTYPE, **fields})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _day(rng, month_start, last_day):
	return date(month_start.year, month_start.month, rng.randint(1, last_day))


def _pick(rng, weights):
	return rng.choices(list(weights), weights=list(weights.values()))[0]


def _name_pool(rng):
	pool = [f"{c}{b}{ind}有限公司" for c in CITIES for b in BRANDS for ind in INDUSTRIES]
	rng.shuffle(pool)
	return pool
