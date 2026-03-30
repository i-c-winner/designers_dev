from __future__ import annotations

import time

import frappe
from frappe.model.document import Document


class TenderBudget(Document):
    def _archive_previous_versions(self):
        if not self.tender_request or not self.name:
            return

        # Retry helps under concurrent edits from UI/list views.
        for attempt in range(3):
            try:
                frappe.db.sql(
                    """
                    update `tabTender Budget`
                    set status = 'Archived'
                    where tender_request = %s
                      and name != %s
                      and status != 'Archived'
                    """,
                    (self.tender_request, self.name),
                )
                return
            except frappe.QueryDeadlockError:
                if attempt == 2:
                    raise
                time.sleep(0.2)

    def validate(self):
        if not self.tender_request:
            return

        latest_version = frappe.db.sql(
            """
            select coalesce(max(version), 0)
            from `tabTender Budget`
            where tender_request = %s
            """,
            (self.tender_request,),
        )[0][0]

        # Any non-latest version must always stay archived.
        if self.version and int(self.version) < int(latest_version):
            self.status = "Archived"

    def before_insert(self):
        if not self.tender_request:
            frappe.throw("Tender Request is required")

        # Keep track of previous latest record for deterministic archive.
        self.flags.previous_latest_budget = frappe.db.get_value(
            "Tender Budget",
            {"tender_request": self.tender_request},
            "name",
            order_by="version desc",
        )

        max_version = frappe.db.sql(
            """
            select coalesce(max(version), 0)
            from `tabTender Budget`
            where tender_request = %s
            """,
            (self.tender_request,),
        )[0][0]

        self.version = int(max_version) + 1

    def after_insert(self):
        # Keep only the newest version active.
        # Every previous version for the same Tender Request is archived.
        previous_latest = self.flags.get("previous_latest_budget")
        if previous_latest:
            frappe.db.set_value("Tender Budget", previous_latest, "status", "Archived", update_modified=False)
        self._archive_previous_versions()

    def on_update(self):
        if self.tender_request and self.version:
            # If this document is not the latest one anymore, force archive.
            latest_version = frappe.db.sql(
                """
                select coalesce(max(version), 0)
                from `tabTender Budget`
                where tender_request = %s
                """,
                (self.tender_request,),
            )[0][0]
            if int(self.version) < int(latest_version) and self.status != "Archived":
                self.db_set("status", "Archived", update_modified=False)
            elif int(self.version) == int(latest_version):
                # Re-apply invariant on any update of the latest version.
                self._archive_previous_versions()

        if self.tender_request:
            frappe.db.set_value("Tender Request", self.tender_request, "budget_version", self.version, update_modified=False)
