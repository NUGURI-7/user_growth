"""Demo data for Subscription Event.

Generates ~21 months of subscribe / churn events ending today, so the report
and dashboard always have a populated "current month". A fixed random seed
keeps the shape of the data identical on every install.

Two business events are planted so the charts tell a story (months are
counted back from the install month):
- Marketing campaign, 7 months ago: new subscriptions jump, mostly via Website
- Basic plan price increase, 4 months ago: Basic churn spikes, reason "Price"

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

CAMPAIGN_MONTHS_AGO = 7
PRICE_INCREASE_MONTHS_AGO = 4

PLAN_FEES = {
	"Basic": [99],
	"Professional": [299],
	"Enterprise": [999, 1499, 1999],
}
PLAN_WEIGHTS = {"Basic": 55, "Professional": 33, "Enterprise": 12}
# Expected monthly churn rate per plan; the actual rate varies ±15% per month
PLAN_CHURN_RATE = {"Basic": 0.05, "Professional": 0.03, "Enterprise": 0.015}

CHANNEL_WEIGHTS = {"Website": 35, "Direct Sales": 25, "Partner": 20, "Referral": 20}
CAMPAIGN_CHANNEL_WEIGHTS = {"Website": 65, "Direct Sales": 15, "Partner": 10, "Referral": 10}
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
PRICE_INCREASE_REASON_WEIGHTS = {"Price": 75, "Competitor": 15, "Missing Features": 5, "Service Experience": 3, "Business Change": 2}

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

	active = {plan: [] for plan in PLAN_WEIGHTS}  # plan -> [doc name], oldest first
	for i in range(HISTORY_MONTHS + 1):
		months_ago = HISTORY_MONTHS - i
		month_start = getdate(add_months(first_month, i))
		full_days = calendar.monthrange(month_start.year, month_start.month)[1]
		last_day = end.day if months_ago == 0 else full_days
		month_ratio = last_day / full_days  # pro-rate a partial current month

		events = []
		# Churn: only customers who subscribed before this month are eligible
		for plan, names_active in active.items():
			rate = PLAN_CHURN_RATE[plan] * rng.uniform(0.85, 1.15)
			reasons = CHURN_REASON_WEIGHTS[plan]
			if plan == "Basic" and months_ago == PRICE_INCREASE_MONTHS_AGO:
				rate *= 2.5
				reasons = PRICE_INCREASE_REASON_WEIGHTS
			count = min(round(len(names_active) * rate * month_ratio), len(names_active))
			for name in rng.sample(names_active, count):
				events.append(("Churn", _day(rng, month_start, last_day), (plan, name, reasons)))

		campaign = months_ago == CAMPAIGN_MONTHS_AGO
		for _ in range(_new_count(rng, i, month_start, month_ratio, campaign)):
			events.append(("Subscribe", _day(rng, month_start, last_day), campaign))

		# Chronological order; on the same day, subscribe before churn
		events.sort(key=lambda e: (e[1], e[0] != "Subscribe"))
		for event_type, event_date, extra in events:
			if event_type == "Subscribe":
				plan = _pick(rng, PLAN_WEIGHTS)
				doc = _create(
					event_type="Subscribe",
					event_date=event_date,
					customer_name=names.pop(),
					plan=plan,
					monthly_fee=rng.choice(PLAN_FEES[plan]),
					channel=_pick(rng, CAMPAIGN_CHANNEL_WEIGHTS if extra else CHANNEL_WEIGHTS),
					region=_pick(rng, REGION_WEIGHTS),
				)
				active[plan].append(doc.name)
			else:
				plan, name, reasons = extra
				_create(
					event_type="Churn",
					event_date=event_date,
					subscription=name,
					churn_reason=_pick(rng, reasons),
				)
				active[plan].remove(name)


def _new_count(rng, month_index, month_start, month_ratio, campaign):
	# Steady growth from ~20 to ~45 per month, dip around Chinese New Year
	base = 20 + month_index * 1.25
	if month_start.month == 2:
		base *= 0.7
	if campaign:
		base *= 1.7
	return round(base * rng.uniform(0.9, 1.1) * month_ratio)


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
