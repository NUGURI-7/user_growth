frappe.pages["user-growth-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("User Growth Dashboard"),
		single_column: true,
	});
	wrapper.dashboard = new UserGrowthDashboard(wrapper);
};

frappe.pages["user-growth-dashboard"].on_page_show = function (wrapper) {
	wrapper.dashboard && wrapper.dashboard.refresh();
};

const DOCTYPE = "Subscription Event";
// Field values (plans, channels, ...) translate in the doctype's context, like the form does
const t = (value) => __(value, null, DOCTYPE);
const ROUTE = "user-growth-dashboard";
const REFRESH_INTERVAL = 5 * 60 * 1000;
const THEME_SETTING = "dashboard_theme";
const PALETTE = ["#4f8cff", "#22d3ee", "#a78bfa", "#f59e0b", "#34d399"];
const GREEN = "#34d399";
const RED = "#f87171";

class UserGrowthDashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.state = { months: 12, plan: null, channel: null, region: null, trend: "customers" };
		this.currency = frappe.boot.sysdefaults.currency;
		this.charts = {};

		this.wrapper.addClass("ug-page");
		this.$root = $(this.template()).appendTo(this.wrapper.find(".layout-main-section"));
		this.bind_events();
		this.load_theme();
		this.timer = setInterval(() => {
			if (frappe.get_route_str() === ROUTE && !document.hidden) this.refresh();
		}, REFRESH_INTERVAL);
	}

	// ---------- data ----------

	refresh() {
		this.$root.addClass("is-loading");
		frappe
			.call({
				method: "user_growth.api.get_dashboard_data",
				args: {
					months: this.state.months,
					plan: this.state.plan,
					channel: this.state.channel,
					region: this.state.region,
				},
			})
			.then((r) => {
				this.data = r.message;
				this.render();
			})
			.always(() => this.$root.removeClass("is-loading"));
	}

	render() {
		const d = this.data;
		this.$root.find(".ug-updated").text(
			__("Updated {0} · auto refresh every 5 min", [moment(d.as_of).format("HH:mm")])
		);
		this.render_filters();
		this.render_kpis();
		this.render_trend();
		this.render_movement();
		this.render_plans();
		this.render_ranking(".ug-channels", d.channels, "channel");
		this.render_ranking(".ug-regions", d.regions, "region");
		this.render_ranking(".ug-reasons", d.churn_reasons, "churn_reason");
		this.render_recent();
	}

	// ---------- sections ----------

	render_filters() {
		const chips = ["plan", "channel", "region"]
			.filter((key) => this.state[key])
			.map(
				(key) => `<button class="ug-chip" data-key="${key}">
					${__(frappe.model.unscrub(key))}: ${t(this.state[key])}
					<span class="ug-chip-x">×</span>
				</button>`
			);
		this.$root.find(".ug-chips").html(chips.join(""));
		this.$root.find(".ug-range button").each((_, el) => {
			$(el).toggleClass("active", Number(el.dataset.months) === this.state.months);
		});
	}

	render_kpis() {
		const k = this.data.kpis;
		const cards = [
			{ key: "active", label: __("Active Customers"), fmt: (v) => format_number(v, null, 0), good: "up", compare: __("vs last month end") },
			{ key: "mrr", label: __("Monthly Recurring Revenue"), fmt: (v) => this.money(v), good: "up", compare: __("vs last month end") },
			{ key: "new", label: __("New This Month"), fmt: (v) => format_number(v, null, 0), good: "up", compare: __("vs same days last month") },
			{ key: "churned", label: __("Churned This Month"), fmt: (v) => format_number(v, null, 0), good: "down", compare: __("vs same days last month") },
		];
		const html = cards.map((c) => {
			const { value, previous } = k[c.key];
			const diff = value - previous;
			let delta = `<span class="ug-delta flat">— ${c.compare}</span>`;
			if (diff !== 0) {
				const better = (diff > 0) === (c.good === "up");
				const pct = previous ? ` (${Math.abs((diff * 100) / previous).toFixed(1)}%)` : "";
				delta = `<span class="ug-delta ${better ? "good" : "bad"}">
					${diff > 0 ? "▲" : "▼"} ${c.fmt(Math.abs(diff))}${pct}
					<span class="ug-muted">${c.compare}</span></span>`;
			}
			return `<div class="ug-card ug-kpi" data-kpi="${c.key}" title="${__("Click to view records")}">
				<div class="ug-kpi-label">${c.label}</div>
				<div class="ug-kpi-value">${c.fmt(value)}</div>
				${delta}
			</div>`;
		});
		this.$root.find(".ug-kpis").html(html.join(""));
	}

	render_trend() {
		const rows = this.data.trend;
		const is_mrr = this.state.trend === "mrr";
		this.$root.find(".ug-trend-toggle button").each((_, el) => {
			$(el).toggleClass("active", el.dataset.trend === this.state.trend);
		});
		this.chart(".ug-trend-chart", {
			type: "line",
			height: 260,
			colors: [PALETTE[0]],
			data: {
				labels: rows.map((r) => this.month_label(r.month)),
				datasets: [
					{
						name: is_mrr ? __("MRR") : __("Active Customers"),
						values: rows.map((r) => (is_mrr ? r.mrr : r.active_customers)),
					},
				],
			},
			// No spline: frappe-charts' spline + regionFill emits NaN paths
			lineOptions: { regionFill: 1, dotSize: 3 },
			axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
			tooltipOptions: {
				// Read state at hover time; the chart is created once and reused
				formatTooltipY: (v) => (this.state.trend === "mrr" ? this.money(v) : format_number(v, null, 0)),
			},
		});
	}

	render_movement() {
		// Complete months only; the current month is still in progress
		const rows = this.data.trend.slice(0, -1);
		this.chart(".ug-movement-chart", {
			type: "bar",
			height: 240,
			colors: [GREEN, RED],
			data: {
				labels: rows.map((r) => this.month_label(r.month)),
				datasets: [
					{ name: t("New"), values: rows.map((r) => r.new_customers) },
					{ name: t("Churned"), values: rows.map((r) => r.churned_customers) },
				],
			},
			barOptions: { spaceRatio: 0.45 },
			axisOptions: { xIsSeries: 1 },
		});
	}

	render_plans() {
		const plans = this.data.plans;
		const total = plans.reduce((s, p) => s + p.count, 0);
		this.chart(".ug-plan-chart", {
			type: "donut",
			height: 220,
			colors: PALETTE,
			data: {
				labels: plans.map((p) => t(p.label)),
				datasets: [{ values: plans.map((p) => p.count) }],
			},
		});

		const legend = plans.map((p, i) => {
			const share = total ? ((p.count * 100) / total).toFixed(1) : 0;
			return `<button class="ug-legend-item ${this.dim_class("plan", p.label)}" data-dim="plan" data-value="${p.label}">
				<span class="ug-dot" style="background:${PALETTE[i % PALETTE.length]}"></span>
				<span class="ug-legend-label">${t(p.label)}</span>
				<span class="ug-legend-value">${p.count}<span class="ug-muted"> · ${share}%</span></span>
				<span class="ug-legend-sub">${this.money(p.mrr)} / ${__("month")}</span>
			</button>`;
		});
		this.$root.find(".ug-plan-legend").html(legend.join("") || this.empty());
	}

	render_ranking(selector, items, dim) {
		const max = Math.max(...items.map((i) => i.count), 1);
		const color = dim === "churn_reason" ? RED : PALETTE[0];
		const html = items.map(
			(item) => `<button class="ug-rank ${this.dim_class(dim, item.label)}" data-dim="${dim}" data-value="${item.label}">
				<div class="ug-rank-head">
					<span>${t(item.label)}</span>
					<span class="ug-rank-value">${item.count}</span>
				</div>
				<div class="ug-bar"><div style="width:${(item.count * 100) / max}%;background:${color}"></div></div>
			</button>`
		);
		this.$root.find(selector).html(html.join("") || this.empty());
	}

	render_recent() {
		const rows = this.data.recent.map((r) => {
			const churn = r.event_type === "Churn";
			return `<button class="ug-recent-row" data-name="${r.name}">
				<span class="ug-muted">${frappe.datetime.str_to_user(r.event_date)}</span>
				<span class="ug-recent-name">${frappe.utils.escape_html(r.customer_name)}</span>
				<span class="ug-muted">${t(r.plan)}</span>
				<span class="ug-badge ${churn ? "bad" : "good"}">${churn ? t("Churn") : t("Subscribe")}</span>
				<span class="ug-recent-extra">${churn ? t(r.churn_reason) : this.money(r.monthly_fee)}</span>
			</button>`;
		});
		this.$root.find(".ug-recent").html(rows.join("") || this.empty());
	}

	// ---------- interactions ----------

	bind_events() {
		const $r = this.$root;

		$r.on("click", ".ug-range button", (e) => {
			this.state.months = Number(e.currentTarget.dataset.months);
			this.refresh();
		});
		$r.on("click", ".ug-trend-toggle button", (e) => {
			this.state.trend = e.currentTarget.dataset.trend;
			this.render_trend();
		});
		// Cross-filter: click a plan / channel / region to filter the whole page
		$r.on("click", "[data-dim]:not([data-dim=churn_reason])", (e) => {
			const { dim, value } = e.currentTarget.dataset;
			this.state[dim] = this.state[dim] === value ? null : value;
			this.refresh();
		});
		$r.on("click", ".ug-chip", (e) => {
			this.state[e.currentTarget.dataset.key] = null;
			this.refresh();
		});
		// Drill-down: open the matching records
		$r.on("click", "[data-dim=churn_reason]", (e) => {
			this.open_list({
				event_type: "Churn",
				churn_reason: e.currentTarget.dataset.value,
				event_date: [">=", this.data.from_date],
			});
		});
		$r.on("click", ".ug-kpi", (e) => {
			const month_start = this.data.kpis.month_start;
			const filters = {
				active: { event_type: "Subscribe", status: "Active" },
				mrr: { event_type: "Subscribe", status: "Active" },
				new: { event_type: "Subscribe", event_date: [">=", month_start] },
				churned: { event_type: "Churn", event_date: [">=", month_start] },
			}[e.currentTarget.dataset.kpi];
			this.open_list(filters);
		});
		$r.on("click", ".ug-recent-row", (e) => {
			frappe.set_route("Form", DOCTYPE, e.currentTarget.dataset.name);
		});

		$r.on("click", ".ug-theme button", (e) => {
			this.set_theme(e.currentTarget.dataset.theme);
			frappe.model.user_settings.save(DOCTYPE, THEME_SETTING, this.theme);
		});
		$r.on("click", ".ug-btn-refresh", () => this.refresh());
		$r.on("click", ".ug-btn-fullscreen", () => {
			if (document.fullscreenElement) document.exitFullscreen();
			else this.$root[0].requestFullscreen();
		});
		$(document).on("fullscreenchange", () => {
			this.$root.toggleClass("is-fullscreen", document.fullscreenElement === this.$root[0]);
			// Charts measure their container on render
			this.data && setTimeout(() => this.render(), 100);
		});
	}

	// The dashboard has its own theme, independent of Frappe's desk theme.
	// The choice is remembered per user in User Settings.
	load_theme() {
		this.set_theme("dark");
		frappe.model.user_settings.get(DOCTYPE).then((settings) => {
			if (settings[THEME_SETTING]) this.set_theme(settings[THEME_SETTING]);
		});
	}

	set_theme(theme) {
		this.theme = theme === "light" ? "light" : "dark";
		this.wrapper.attr("data-ug-theme", this.theme);
		this.$root.find(".ug-theme button").each((_, el) => {
			$(el).toggleClass("active", el.dataset.theme === this.theme);
		});
	}

	open_list(filters) {
		const dims = {};
		["plan", "channel", "region"].forEach((k) => this.state[k] && (dims[k] = this.state[k]));
		frappe.route_options = { docstatus: 1, ...dims, ...filters };
		frappe.set_route("List", DOCTYPE);
	}

	// ---------- helpers ----------

	chart(selector, options) {
		// Create once, then update in place: frappe-charts' destroy() leaves a
		// resize observer behind, so re-creating charts leaks stale redraws.
		if (this.charts[selector]) {
			this.charts[selector].update(options.data);
			return;
		}
		const el = this.$root.find(selector)[0];
		this.charts[selector] = new frappe.Chart(el, {
			animate: 0,
			// The entry animation swaps the SVG for a clone; a resize during the swap throws
			disableEntryAnimation: 1,
			truncateLegends: 1,
			...options,
		});
	}

	dim_class(dim, value) {
		if (!this.state[dim]) return "";
		return this.state[dim] === value ? "selected" : "dimmed";
	}

	money(value) {
		return format_currency(value, this.currency, 0);
	}

	month_label(month) {
		return moment(month, "YYYY-MM").format("YY/MM");
	}

	empty() {
		return `<div class="ug-empty">${__("No data")}</div>`;
	}

	template() {
		const card = (cls, title, body, extra = "") => `
			<div class="ug-card ${cls}">
				<div class="ug-card-head"><span class="ug-card-title">${title}</span>${extra}</div>
				${body}
			</div>`;
		return `<div class="ug-dash">
			<div class="ug-header">
				<div>
					<div class="ug-title">${__("User Growth Dashboard")}</div>
					<div class="ug-updated ug-muted"></div>
				</div>
				<div class="ug-toolbar">
					<div class="ug-chips"></div>
					<div class="ug-segment ug-range">
						<button data-months="6">${__("6 Months")}</button>
						<button data-months="12">${__("12 Months")}</button>
						<button data-months="0">${__("All")}</button>
					</div>
					<div class="ug-segment ug-theme">
						<button data-theme="dark">${__("Dark")}</button>
						<button data-theme="light">${__("Light")}</button>
					</div>
					<button class="ug-icon-btn ug-btn-refresh" title="${__("Refresh")}">${frappe.utils.icon("refresh", "sm")}</button>
					<button class="ug-icon-btn ug-btn-fullscreen" title="${__("Full Screen")}">${frappe.utils.icon("expand", "sm")}</button>
				</div>
			</div>

			<div class="ug-grid ug-kpis"></div>

			<div class="ug-grid">
				${card(
					"span-8",
					__("Growth Trend"),
					`<div class="ug-trend-chart"></div>`,
					`<div class="ug-segment ug-trend-toggle">
						<button data-trend="customers">${__("Customers")}</button>
						<button data-trend="mrr">${__("MRR")}</button>
					</div>`
				)}
				${card(
					"span-4",
					__("Active Customers by Plan"),
					`<div class="ug-plan-chart"></div><div class="ug-plan-legend"></div>`
				)}
			</div>

			<div class="ug-grid">
				${card("span-6", __("New vs Churned"), `<div class="ug-movement-chart"></div>`)}
				${card("span-3", __("New by Channel"), `<div class="ug-channels"></div>`)}
				${card("span-3", __("Churn Reasons"), `<div class="ug-reasons"></div>`)}
			</div>

			<div class="ug-grid">
				${card("span-4", __("Active Customers by Region"), `<div class="ug-regions"></div>`)}
				${card("span-8", __("Recent Activity"), `<div class="ug-recent"></div>`)}
			</div>

			<div class="ug-footnote ug-muted">
				${__("Tip: click a plan, channel or region to filter the whole dashboard; click a KPI card or churn reason to open the records.")}
			</div>
		</div>`;
	}
}
