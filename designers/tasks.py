from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, today


def check_deadlines() -> None:
    tomorrow = add_to_date(today(), days=1)

    due_tenders = frappe.get_all(
        "Tender Request",
        filters={
            "deadline": ["<=", tomorrow],
            "status": ["not in", ["Rejected", "Sent to Client"]],
        },
        fields=["name", "deadline", "assigned_to"],
    )

    for tender in due_tenders:
        if not tender.assigned_to:
            continue

        frappe.sendmail(
            recipients=[tender.assigned_to],
            subject=_("Tender deadline alert: {0}").format(tender.name),
            message=_("Tender <b>{0}</b> has deadline <b>{1}</b>.").format(tender.name, tender.deadline),
            now=False,
        )
