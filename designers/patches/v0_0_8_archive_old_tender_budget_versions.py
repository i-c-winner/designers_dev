from __future__ import annotations

import frappe


def execute():
    frappe.db.sql(
        """
        update `tabTender Budget` tb
        inner join (
            select tender_request, max(version) as max_version
            from `tabTender Budget`
            where ifnull(tender_request, '') != ''
            group by tender_request
            having count(*) > 1
        ) latest on latest.tender_request = tb.tender_request
        set tb.status = 'Archived'
        where tb.version < latest.max_version
          and tb.status != 'Archived'
        """
    )
