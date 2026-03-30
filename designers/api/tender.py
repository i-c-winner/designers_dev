from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe import _
from designers.services.notification_service import notify_new_website_request


def _parse_data(data: str | dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    if isinstance(data, dict):
        return data
    return frappe.parse_json(data)


def _get_or_create_customer(customer_name: str, email: str | None = None) -> str:
    existing = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
    if existing:
        return existing

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Company",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
        }
    ).insert(ignore_permissions=True)

    if email:
        contact = frappe.get_doc(
            {
                "doctype": "Contact",
                "first_name": customer_name,
                "email_ids": [{"email_id": email, "is_primary": 1}],
                "links": [{"link_doctype": "Customer", "link_name": customer.name}],
            }
        )
        contact.insert(ignore_permissions=True)

    return customer.name


@frappe.whitelist(allow_guest=True)
def create_tender_from_website(data: str | dict[str, Any] | None = None) -> dict[str, str]:
    payload = _parse_data(data)

    client_name = payload.get("client_name")
    if not client_name:
        frappe.throw(_("client_name is required"))

    customer = _get_or_create_customer(client_name, payload.get("email"))

    doc = frappe.get_doc(
        {
            "doctype": "Tender Request",
            "project_prefix": payload.get("project_prefix") or "WEB",
            "project_type": payload.get("project_type") or "General",
            "client": customer,
            "source": "Website",
            "website_request_id": payload.get("website_request_id") or frappe.generate_hash(length=10),
            "deadline": payload.get("deadline"),
            "status": "New Request",
            "description": payload.get("description"),
        }
    ).insert(ignore_permissions=True)
    notify_new_website_request(doc)

    attachments = payload.get("attachments") or []
    for item in attachments:
        file_name = item.get("file_name") or "attachment.bin"
        content = item.get("content")
        if not content:
            continue

        try:
            binary = base64.b64decode(content)
        except Exception:
            binary = content.encode()

        frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "content": binary,
                "decode": False,
                "is_private": 1,
            }
        ).insert(ignore_permissions=True)

    return {
        "tender_request": doc.name,
        "website_request_id": doc.website_request_id,
        "status": doc.status,
    }


@frappe.whitelist()
def get_tender_status(tender_request: str) -> dict[str, Any]:
    doc = frappe.get_doc("Tender Request", tender_request)
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Authentication required"))

    if "Website User" in frappe.get_roles(user):
        if doc.assigned_to != user and doc.owner != user:
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    return {
        "name": doc.name,
        "status": doc.status,
        "deadline": doc.deadline,
        "budget_version": doc.budget_version,
        "assigned_to": doc.assigned_to,
    }


@frappe.whitelist()
def upload_file_to_tender(
    tender_request: str,
    file_name: str,
    content_base64: str,
    is_private: int = 1,
) -> dict[str, str]:
    doc = frappe.get_doc("Tender Request", tender_request)

    content = base64.b64decode(content_base64)
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name,
            "content": content,
            "decode": False,
            "is_private": int(is_private),
        }
    ).insert(ignore_permissions=True)

    return {"file_url": file_doc.file_url, "name": file_doc.name}


@frappe.whitelist()
def approve_budget(tender_budget: str, comment: str | None = None) -> dict[str, str]:
    budget = frappe.get_doc("Tender Budget", tender_budget)
    budget.approved_by = frappe.session.user
    budget.approved_on = frappe.utils.now_datetime()
    budget.approval_comment = comment
    budget.status = "Approved"
    budget.save(ignore_permissions=True)

    return {"budget": budget.name, "status": budget.status}


@frappe.whitelist()
def create_proposal(tender_request: str, tender_budget: str | None = None) -> dict[str, str]:
    tender = frappe.get_doc("Tender Request", tender_request)
    budget_version = None

    if tender_budget:
        budget = frappe.get_doc("Tender Budget", tender_budget)
        if budget.tender_request != tender.name:
            frappe.throw(_("Selected budget does not belong to this Tender Request"))
        if budget.status != "Approved":
            frappe.throw(_("Tender Budget must be Approved before creating Commercial Proposal"))
    else:
        tender_budget = frappe.db.get_value(
            "Tender Budget",
            {"tender_request": tender.name, "status": "Approved"},
            "name",
            order_by="version desc",
        )
        if not tender_budget:
            frappe.throw(_("No approved budget found"))
        budget = frappe.get_doc("Tender Budget", tender_budget)

    budget_version = budget.version

    proposal = frappe.get_doc(
        {
            "doctype": "Commercial Proposal",
            "tender_request": tender.name,
            "tender_budget": tender_budget,
            "budget_version": budget_version,
            "status": "Draft",
        }
    ).insert(ignore_permissions=True)

    return {"proposal": proposal.name, "status": proposal.status}
