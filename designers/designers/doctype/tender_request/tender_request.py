from __future__ import annotations

import re

import frappe
from frappe.model.document import Document

from designers.services.notification_service import notify_status_change
from designers.services.tender_service import assign_next_user, create_project_structure, make_project_name

PHONE_REGEX = re.compile(r"^\+7-(?:\d{3}|\(\d{3}\))-\d{3}-\d{2}-\d{2}$")
PHONE_HINT = "Формат телефона: +7-999-123-45-67 или +7-(999)-123-45-67"


class TenderRequest(Document):
    def validate(self):
        if self.contact_phone and not PHONE_REGEX.fullmatch(self.contact_phone.strip()):
            frappe.throw(PHONE_HINT)

    def before_insert(self):
        if not self.source and frappe.session.user == "Guest":
            self.source = "Website"

        if not self.request_date:
            self.request_date = frappe.utils.today()

        if not self.project_name:
            self.project_name = make_project_name(self.project_prefix, self.project_type)

        if not self.status:
            self.status = "New Request"

    def after_insert(self):
        create_project_structure(self.project_name, owner=self.owner)

    def on_update(self):
        assign_next_user(self)
        notify_status_change(self)


@frappe.whitelist()
def send_to_client(tender_request: str):
    doc = frappe.get_doc("Tender Request", tender_request)

    if not doc.client:
        frappe.throw("Customer is required to send proposal")

    recipients = []
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
        (doc.client,),
        as_dict=True,
    )
    if customer_contacts:
        recipients.append(customer_contacts[0].email_id)

    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=f"Commercial proposal for {doc.project_name}",
            message=f"Tender {doc.name} has a new commercial proposal.",
            now=False,
        )

    doc.status = "Sent to Client"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}
