from __future__ import annotations

import frappe
from frappe.model.document import Document


class CommercialProposal(Document):
    def validate(self):
        if self.tender_budget:
            self.budget_version = frappe.db.get_value("Tender Budget", self.tender_budget, "version")


@frappe.whitelist()
def send_to_client(proposal_name: str):
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    tender = frappe.get_doc("Tender Request", proposal.tender_request)

    if not tender.client:
        frappe.throw("Customer is required")

    customer_contacts = frappe.db.sql(
        """
        select ce.email_id
        from `tabContact Email` ce
        inner join `tabDynamic Link` dl on dl.parent = ce.parent and dl.parenttype = 'Contact'
        where dl.link_doctype = 'Customer'
          and dl.link_name = %s
          and ifnull(ce.is_primary, 0) = 1
        limit 1
        """,
        (tender.client,),
        as_dict=True,
    )

    if customer_contacts:
        frappe.sendmail(
            recipients=[customer_contacts[0].email_id],
            subject=f"Commercial Proposal: {proposal.name}",
            message=f"Your commercial proposal for tender {tender.name} is ready.",
            now=False,
        )

    proposal.sent_to_client = 1
    proposal.sent_on = frappe.utils.now_datetime()
    proposal.status = "Sent"
    proposal.save(ignore_permissions=True)

    tender.status = "Sent to Client"
    tender.save(ignore_permissions=True)

    return {"proposal": proposal.name, "status": proposal.status}
