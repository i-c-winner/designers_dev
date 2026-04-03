from __future__ import annotations

import json

import frappe
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils.file_manager import save_file
from frappe.utils import now_datetime, today


class CommercialProposal(Document):
    PARENT_STATUS_BY_PROPOSAL_STATUS = {
        "Draft": "Proposal Drafting",
        "Under Approval": "Proposal Review",
        "Approved": "Proposal Review",
        "Admin Review": "Proposal Review",
        "Admin Approved": "Proposal Approved",
        "Sent": "Sent to Client",
        "Rejected": "Rejected",
    }

    def validate(self):
        # Keep compatibility with sites where these fields were removed from DocType.
        if not self.meta.has_field("tender_budget"):
            return

        tender_budget = self.get("tender_budget")
        if tender_budget and self.meta.has_field("budget_version"):
            self.budget_version = frappe.db.get_value("Tender Budget", tender_budget, "version")

    def before_insert(self):
        _prefill_print_format_fields(self)

    def on_update(self):
        if not self.tender_request:
            return
        parent_status = self.PARENT_STATUS_BY_PROPOSAL_STATUS.get(self.status)
        if parent_status:
            frappe.db.set_value("Tender Request", self.tender_request, "status", parent_status, update_modified=False)

        # Ensure workflow transition to "Sent" actually sends email with attachments.
        if self.status == "Sent" and not int(self.get("sent_to_client") or 0):
            tender = frappe.get_doc("Tender Request", self.tender_request)
            _send_proposal_email_to_customer(self, tender)
            self.db_set("sent_to_client", 1, update_modified=False)
            self.db_set("sent_on", now_datetime(), update_modified=False)


def _prefill_print_format_fields(proposal: "CommercialProposal") -> None:
    tender = None
    tender_request_name = (proposal.get("tender_request") or "").strip()
    if tender_request_name and frappe.db.exists("Tender Request", tender_request_name):
        tender = frappe.get_doc("Tender Request", tender_request_name)

    def set_if_empty(fieldname: str, value):
        if value in (None, ""):
            return
        if proposal.meta.has_field(fieldname) and not proposal.get(fieldname):
            proposal.set(fieldname, value)

    set_if_empty("city", "Tashkent")
    set_if_empty("document_date", today())
    set_if_empty("company_name", "Designers")
    set_if_empty("document_theme", tender.get("project_type") if tender else "")
    set_if_empty("project_object", tender.get("project_name") if tender else "")
    set_if_empty("recipient_company", tender.get("client") if tender else "")
    set_if_empty("recipient_name", tender.get("connect_user") if tender else "")
    set_if_empty(
        "offer_subject",
        f"Коммерческое предложение по проекту {(tender.get('project_name') or '').strip()}".strip()
        if tender
        else "Коммерческое предложение",
    )
    set_if_empty("cover_letter_intro", tender.get("description") if tender else "")
    set_if_empty("document_number", proposal.name or "")

    # Keep JSON collections initialized as valid arrays to simplify print format input.
    json_array_fields = [
        "company_services_json",
        "competencies_json",
        "offer_goals_json",
        "stages_json",
        "abbreviations_json",
        "preproject_rows_json",
        "project_rows_json",
        "working_rows_page1_json",
        "working_rows_page2_json",
        "cost_summary_json",
        "excluded_costs_json",
        "page5_links_json",
        "page5_terms_json",
        "page5_extra_left_json",
        "page5_extra_right_json",
        "guarantees_json",
        "responsibility_points_json",
    ]
    for fieldname in json_array_fields:
        if proposal.meta.has_field(fieldname):
            value = (proposal.get(fieldname) or "").strip()
            if not value:
                proposal.set(fieldname, "[]")
                continue
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, list):
                    proposal.set(fieldname, "[]")
            except Exception:
                proposal.set(fieldname, "[]")


def _build_email_attachments(proposal: CommercialProposal) -> list[dict]:
    try:
        print_format = frappe.db.get_value(
            "Print Format",
            {"doc_type": "Commercial Proposal", "disabled": 0, "name": "Commercial Proposal"},
            "name",
        ) or "Commercial Proposal"
        pdf_content = frappe.get_print(
            doctype="Commercial Proposal",
            name=proposal.name,
            print_format=print_format,
            as_pdf=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Commercial Proposal PDF generation failed")
        frappe.throw("Не удалось сформировать PDF Commercial Proposal. Письмо клиенту не отправлено.")

    if not pdf_content:
        frappe.throw("PDF Commercial Proposal пустой. Письмо клиенту не отправлено.")

    attachment_name = f"{proposal.name}-{now_datetime().strftime('%Y%m%d-%H%M%S')}.pdf"

    try:
        save_file(
            fname=attachment_name,
            content=pdf_content,
            dt="Commercial Proposal",
            dn=proposal.name,
            is_private=1,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Commercial Proposal PDF save failed")
        frappe.throw("PDF сформирован, но не удалось сохранить его в документ. Письмо не отправлено.")

    return [{"fname": attachment_name, "fcontent": pdf_content}]

def _get_primary_customer_email(customer_name: str | None) -> str | None:
    if not customer_name:
        return None

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
        (customer_name,),
        as_dict=True,
    )
    if not customer_contacts:
        return None
    return customer_contacts[0].email_id


def _send_proposal_email_to_customer(
    proposal: CommercialProposal,
    tender,
    *,
    subject: str | None = None,
    send_now: bool = False,
) -> None:
    if not tender.client:
        frappe.throw("Customer is required")

    recipient = _get_primary_customer_email(tender.client)
    if not recipient:
        frappe.throw("Primary customer email is required")

    attachments = _build_email_attachments(proposal)
    frappe.sendmail(
        recipients=[recipient],
        subject=subject or f"Commercial Proposal: {proposal.name}",
        message=f"Your commercial proposal for tender {tender.name} is ready.",
        attachments=attachments,
        reference_doctype="Commercial Proposal",
        reference_name=proposal.name,
        now=send_now,
    )
    # frappe.sendmail(
    #     recipients=[recipient],
    #     subject=f"Commercial Proposal: {proposal.name}",
    #     message=f"Your commercial proposal for tender {tender.name} is ready.",
    #     attachments=attachments,
    #     reference_doctype="Commercial Proposal",
    #     reference_name=proposal.name,
    #     now=False,
    # )
    # frappe.sendmail(
    #     recipients=[recipient],
    #     subject=f"Commercial Proposal: {proposal.name}",
    #     message=f"Your commercial proposal for tender {tender.name} is ready.",
    #     attachments=attachments,
    #     now=False,
    # )


@frappe.whitelist()
def send_to_client(proposal_name: str):
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    tender = frappe.get_doc("Tender Request", proposal.tender_request)

    # Apply workflow transition instead of forcing status assignment.
    # Direct assignment can fail with "Workflow State transition not allowed".
    proposal = apply_workflow(proposal, "Send To Client")
    proposal.reload()

    # Keep parent status in sync without invoking another workflow transition.
    if tender.status != "Sent to Client":
        frappe.db.set_value("Tender Request", tender.name, "status", "Sent to Client", update_modified=False)

    return {"proposal": proposal.name, "status": proposal.status}


@frappe.whitelist()
def resend_to_client(proposal_name: str):
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    tender = frappe.get_doc("Tender Request", proposal.tender_request)

    resend_subject = f"Commercial Proposal (Resend {now_datetime().strftime('%Y-%m-%d %H:%M:%S')}): {proposal.name}"
    _send_proposal_email_to_customer(proposal, tender, subject=resend_subject, send_now=True)
    proposal.db_set("sent_to_client", 1, update_modified=False)
    proposal.db_set("sent_on", now_datetime(), update_modified=False)

    return {"proposal": proposal.name, "status": proposal.status, "resent": 1}
