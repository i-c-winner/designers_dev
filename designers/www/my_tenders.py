from __future__ import annotations

import frappe


def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Login required")

    context.no_cache = 1
    filters = {}
    if "Website User" in frappe.get_roles(user):
        filters = [["Tender Request", "assigned_to", "=", user]]

    context.tenders = frappe.get_all(
        "Tender Request",
        filters=filters,
        fields=["name", "project_name", "status", "deadline", "source"],
        order_by="modified desc",
        limit=50,
    )
