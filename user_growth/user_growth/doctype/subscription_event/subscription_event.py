# Copyright (c) 2026, nuguri and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class SubscriptionEvent(Document):
	def validate(self):
		if self.event_type == "Subscribe":
			self.subscription = None
			self.churn_reason = None
			if not self.status:
				self.status = "Active"
		else:
			self.status = None
			self.validate_churn()

	def validate_churn(self):
		sub = frappe.db.get_value(
			"Subscription Event",
			self.subscription,
			["event_type", "docstatus", "status", "event_date"],
			as_dict=True,
		)
		if not sub or sub.event_type != "Subscribe" or sub.docstatus != 1:
			frappe.throw(_("Subscription must be a submitted Subscribe event"))
		if sub.status != "Active":
			frappe.throw(_("Subscription {0} has already churned").format(self.subscription))
		if getdate(self.event_date) < getdate(sub.event_date):
			frappe.throw(_("Churn date cannot be earlier than subscription date"))

		duplicate = frappe.db.exists(
			"Subscription Event",
			{
				"subscription": self.subscription,
				"event_type": "Churn",
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
		)
		if duplicate:
			frappe.throw(_("Churn event {0} already exists for this subscription").format(duplicate))

	def on_submit(self):
		if self.event_type == "Churn":
			frappe.db.set_value("Subscription Event", self.subscription, "status", "Churned")

	def on_cancel(self):
		if self.event_type == "Churn":
			frappe.db.set_value("Subscription Event", self.subscription, "status", "Active")
