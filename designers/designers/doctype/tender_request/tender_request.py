from __future__ import annotations

import re

import frappe
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import now

from designers.permissions.common import get_roles, is_super_user, user_has_tender_access
from designers.services.tender_service import assign_next_user, create_project_structure, make_project_name

PHONE_REGEX = re.compile(r"^\+7-(?:\d{3}|\(\d{3}\))-\d{3}-\d{2}-\d{2}$")
PHONE_HINT = "Формат телефона: +7-999-123-45-67 или +7-(999)-123-45-67"
INITIAL_WORKFLOW_STATUS = "New Request"
LOCKED_FIELDS_AFTER_FIRST_ACTION = {
    "contact_name",
    "contact_phone",
    "project_name",
    "request_date",
    "project_prefix",
    "project_type",
    "client",
    "source",
    "website_request_id",
    "deadline",
    "description",
}
START_WORK_REQUIRED_OPTIONAL_FIELDS = (
    "project_prefix",
    "project_type",
    "client",
    "source",
    "description",
    "deadline",
)


class TenderRequest(Document):
    def validate(self):
        if self.contact_phone and not PHONE_REGEX.fullmatch(self.contact_phone.strip()):
            frappe.throw(PHONE_HINT)
        self._sync_nested_docs_links()
        self._validate_approved_dependencies()
        self._prepare_start_work_transition()
        self._validate_locked_fields_after_first_action()

    def _sync_nested_docs_links(self):
        if not self.name:
            return

        latest_budget = frappe.db.get_value(
            "Tender Budget",
            {"tender_request": self.name},
            "name",
            order_by="creation desc",
        )
        latest_proposal = frappe.db.get_value(
            "Commercial Proposal",
            {"tender_request": self.name},
            "name",
            order_by="creation desc",
        )

        if latest_budget and self.get("tender_budget_request") != latest_budget:
            self.tender_budget_request = latest_budget
        if latest_proposal and self.get("commercial_proposal") != latest_proposal:
            self.commercial_proposal = latest_proposal

    def _validate_approved_dependencies(self):
        if (self.status or "").strip() != "Approved":
            return

        budget_name = self.get("tender_budget_request")
        proposal_name = self.get("commercial_proposal")

        missing = []
        not_approved = []

        if not budget_name:
            missing.append("Tender Budget Request")
        if not proposal_name:
            missing.append("Commercial Proposal")

        if budget_name:
            budget_status = frappe.db.get_value("Tender Budget", budget_name, "status")
            if (budget_status or "").strip().lower() != "approved":
                not_approved.append(
                    f"Tender Budget Request ({budget_name}) = {budget_status or 'Пусто'}"
                )

        if proposal_name:
            proposal_status = frappe.db.get_value("Commercial Proposal", proposal_name, "status")
            if (proposal_status or "").strip().lower() != "approved":
                not_approved.append(
                    f"Commercial Proposal ({proposal_name}) = {proposal_status or 'Пусто'}"
                )

        if missing or not_approved:
            parts = []
            if missing:
                parts.append("Не заполнены связанные документы: " + ", ".join(missing))
            if not_approved:
                parts.append("Статусы должны быть Approved: " + "; ".join(not_approved))
            frappe.throw(". ".join(parts))

    def _prepare_start_work_transition(self):
        previous = self.get_doc_before_save()
        if not previous:
            return

        # Run only on Start Work transition: New Request -> In Progress.
        if previous.status != "New Request" or self.status != "In Progress":
            return

        missing: list[str] = []
        for fieldname in START_WORK_REQUIRED_OPTIONAL_FIELDS:
            field = self.meta.get_field(fieldname)
            if not field:
                continue
            value = self.get(fieldname)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field.label or fieldname)

        if missing:
            frappe.throw(
                "Перед Start Work заполните поля: " + ", ".join(missing)
            )

        if not self.project_name:
            self.project_name = make_project_name(self.project_prefix, self.project_type)

        self.flags.create_project_structure_on_update = bool(self.project_name)

    def _validate_locked_fields_after_first_action(self):
        if self.is_new():
            return

        previous = self.get_doc_before_save()
        if not previous:
            return

        # Editing is allowed while the document is still in the very first status.
        # Once it leaves New Request, business fields become immutable.
        if previous.status == INITIAL_WORKFLOW_STATUS:
            return

        changed = [
            field
            for field in LOCKED_FIELDS_AFTER_FIRST_ACTION
            if (previous.get(field) or "") != (self.get(field) or "")
        ]
        if changed:
            frappe.throw(
                "После первого workflow-действия поля заявки нельзя изменять: "
                + ", ".join(sorted(changed))
            )

    def before_insert(self):
        if not self.source and frappe.session.user == "Guest":
            self.source = "Website"

        if not self.request_date:
            self.request_date = frappe.utils.today()

        if not self.status:
            self.status = "New Request"

    def after_insert(self):
        # Project name/folder are created when workflow moves to Start Work (In Progress).
        pass

    def on_update(self):
        if self.flags.get("create_project_structure_on_update"):
            create_project_structure(self.project_name, owner=self.owner)
        assign_next_user(self)
        self._ensure_biz_user_visibility()

    def _ensure_biz_user_visibility(self):
        # Website submissions are created by Guest. Make them visible to all Biz Users.
        if self.owner != "Guest":
            return

        existing_users = set(
            frappe.get_all(
                "Tender Request Access User",
                filters={"parent": self.name, "parenttype": "Tender Request", "parentfield": "access_users"},
                pluck="user",
            )
        )

        biz_users = set(
            frappe.db.sql(
                """
                select distinct hr.parent
                from `tabHas Role` hr
                inner join `tabUser` u on u.name = hr.parent
                where hr.role = 'Biz User'
                  and ifnull(hr.parenttype, 'User') = 'User'
                  and hr.parent not in ('Administrator', 'Guest')
                  and ifnull(u.enabled, 0) = 1
                """,
                pluck=True,
            )
        )

        if self.assigned_to and self.assigned_to not in {"Administrator", "Guest"}:
            biz_users.add(self.assigned_to)

        merged = sorted(existing_users | biz_users)
        if set(merged) != existing_users:
            _replace_access_users(self.name, merged)


def _get_latest_child(doctype: str, tender_request: str):
    name = frappe.db.get_value(
        doctype,
        {"tender_request": tender_request},
        "name",
        order_by="creation desc",
    )
    if not name:
        return None
    return frappe.get_doc(doctype, name)


def _apply_child_workflow_action(doc, action: str):
    return apply_workflow(doc, action)


def _normalize_access_users(users) -> list[str]:
    if users is None:
        return []
    if isinstance(users, str):
        users = frappe.parse_json(users)

    normalized = []
    seen = set()
    for item in users or []:
        user = item.get("user") if isinstance(item, dict) else item
        user = (user or "").strip()
        if not user or user in {"Guest", "Administrator"}:
            continue
        if user in seen:
            continue
        if not frappe.db.get_value("User", user, "name"):
            continue
        seen.add(user)
        normalized.append(user)
    return normalized


def _replace_access_users(tender_request: str, users: list[str]) -> None:
    frappe.db.delete(
        "Tender Request Access User",
        {"parent": tender_request, "parenttype": "Tender Request", "parentfield": "access_users"},
    )
    ts = now()
    for idx, user in enumerate(users, start=1):
        frappe.db.sql(
            """
            insert into `tabTender Request Access User`
            (`name`,`creation`,`modified`,`modified_by`,`owner`,`docstatus`,`idx`,`user`,`parent`,`parentfield`,`parenttype`)
            values (%s,%s,%s,%s,%s,0,%s,%s,%s,'access_users','Tender Request')
            """,
            (
                frappe.generate_hash(length=10),
                ts,
                ts,
                frappe.session.user,
                frappe.session.user,
                idx,
                user,
                tender_request,
            ),
        )
    frappe.db.sql(
        """
        update `tabTender Request`
        set modified = %s, modified_by = %s
        where name = %s
        """,
        (ts, frappe.session.user, tender_request),
    )
    frappe.clear_document_cache("Tender Request", tender_request)


@frappe.whitelist()
def update_access_users(tender_request: str, users=None):
    current_user = frappe.session.user
    if current_user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    roles = get_roles(current_user)
    can_edit = is_super_user(current_user, roles) or ("Biz Manager" in roles)
    if not can_edit:
        frappe.throw("Not permitted", frappe.PermissionError)

    normalized = _normalize_access_users(users)
    _replace_access_users(tender_request, normalized)
    return {"name": tender_request, "access_users": normalized}


def backfill_biz_user_visibility_for_guest_requests():
    names = frappe.get_all("Tender Request", filters={"owner": "Guest"}, pluck="name")
    for name in names:
        doc = frappe.get_doc("Tender Request", name)
        doc._ensure_biz_user_visibility()
    return {"updated": len(names)}


def _has_workflow_action(doc, action: str) -> bool:
    if not doc:
        return False
    try:
        transitions = get_transitions(doc)
    except Exception:
        return False
    return any((t.get("action") or "").strip() == action for t in transitions)


@frappe.whitelist()
def get_action_visibility(tender_request: str):
    tr = frappe.get_doc("Tender Request", tender_request)
    user = frappe.session.user
    roles = get_roles(user)
    is_biz_user = "Biz User" in roles

    can_create_budget_statuses = {
        "New Request",
        "In Progress",
        "Under Review",
        "Budget Drafting",
        "Budget Director Review",
        "Budget CEO Review",
        "Rejected",
    }
    can_create_proposal_statuses = {
        "Budget Approved",
        "Proposal Drafting",
        "Proposal Review",
        "Rejected",
    }

    latest_budget = _get_latest_child("Tender Budget", tr.name)
    latest_proposal = _get_latest_child("Commercial Proposal", tr.name)

    can_create_budget = (
        is_biz_user
        and
        frappe.has_permission("Tender Budget", ptype="create", user=user)
        and tr.status in can_create_budget_statuses
    )
    can_create_proposal = (
        is_biz_user
        and
        frappe.has_permission("Commercial Proposal", ptype="create", user=user)
        and tr.status in can_create_proposal_statuses
        and bool(
            frappe.db.get_value(
                "Tender Budget",
                {"tender_request": tr.name, "status": "Approved"},
                "name",
            )
        )
    )

    return {
        "edit_access": is_super_user(user, roles) or ("Biz Manager" in roles),
        "create_budget": can_create_budget,
        "send_budget_to_director": (
            latest_budget is not None
            and latest_budget.status == "Draft"
            and _has_workflow_action(latest_budget, "Бюджет на согласование")
        ),
        "approve_director": (
            latest_budget is not None
            and latest_budget.status == "Under Director Review"
            and _has_workflow_action(latest_budget, "Согласовать бюджет")
        ),
        "approve_budget": (
            latest_budget is not None
            and latest_budget.status == "Under CEO Review"
            and _has_workflow_action(latest_budget, "Согласовать бюджет")
        ),
        "create_proposal": can_create_proposal,
        "submit_proposal": (
            latest_proposal is not None
            and latest_proposal.status == "Draft"
            and _has_workflow_action(latest_proposal, "КП на согласование")
        ),
        "approve_proposal": (
            latest_proposal is not None
            and latest_proposal.status == "Under Approval"
            and _has_workflow_action(latest_proposal, "Согласовать КП")
        ),
        "send_to_admin": (
            latest_proposal is not None
            and latest_proposal.status == "Approved"
            and _has_workflow_action(latest_proposal, "Согласовать КП")
        ),
        "approve_by_admin": (
            latest_proposal is not None
            and latest_proposal.status == "Admin Review"
            and _has_workflow_action(latest_proposal, "КП на согласование")
        ),
        "send_to_client": (
            latest_proposal is not None
            and latest_proposal.status == "Admin Approved"
            and _has_workflow_action(latest_proposal, "Отправить КП клиенту")
        ),
    }


@frappe.whitelist()
def create_budget_for_request(tender_request: str):
    tr = frappe.get_doc("Tender Request", tender_request)
    budget = frappe.get_doc(
        {
            "doctype": "Tender Budget",
            "tender_request": tr.name,
            "status": "Draft",
        }
    ).insert()
    return {"name": budget.name, "status": budget.status}


@frappe.whitelist()
def send_budget_to_director(tender_request: str):
    budget = _get_latest_child("Tender Budget", tender_request)
    if not budget:
        frappe.throw("Создайте Tender Budget перед отправкой директору")
    updated = _apply_child_workflow_action(budget, "Бюджет на согласование")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def approve_budget_director(tender_request: str):
    budget = _get_latest_child("Tender Budget", tender_request)
    if not budget:
        frappe.throw("Tender Budget не найден")
    updated = _apply_child_workflow_action(budget, "Согласовать бюджет")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def approve_budget_ceo(tender_request: str):
    budget = _get_latest_child("Tender Budget", tender_request)
    if not budget:
        frappe.throw("Tender Budget не найден")
    updated = _apply_child_workflow_action(budget, "Согласовать бюджет")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def create_proposal_for_request(tender_request: str):
    budget = frappe.db.get_value(
        "Tender Budget",
        {"tender_request": tender_request, "status": "Approved"},
        "name",
        order_by="version desc",
    )
    if not budget:
        frappe.throw("Сначала согласуйте Tender Budget (status = Approved)")

    proposal_data = {
        "doctype": "Commercial Proposal",
        "tender_request": tender_request,
        "status": "Draft",
    }
    proposal_meta = frappe.get_meta("Commercial Proposal")
    if proposal_meta.has_field("tender_budget"):
        proposal_data["tender_budget"] = budget
    if proposal_meta.has_field("budget_version"):
        proposal_data["budget_version"] = frappe.db.get_value("Tender Budget", budget, "version")

    proposal = frappe.get_doc(proposal_data).insert()
    return {"name": proposal.name, "status": proposal.status}


@frappe.whitelist()
def submit_proposal_for_approval(tender_request: str):
    proposal = _get_latest_child("Commercial Proposal", tender_request)
    if not proposal:
        frappe.throw("Commercial Proposal не найден")
    updated = _apply_child_workflow_action(proposal, "КП на согласование")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def approve_proposal(tender_request: str):
    proposal = _get_latest_child("Commercial Proposal", tender_request)
    if not proposal:
        frappe.throw("Commercial Proposal не найден")
    updated = _apply_child_workflow_action(proposal, "Согласовать КП")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def send_proposal_to_admin(tender_request: str):
    proposal = _get_latest_child("Commercial Proposal", tender_request)
    if not proposal:
        frappe.throw("Commercial Proposal не найден")
    updated = _apply_child_workflow_action(proposal, "Согласовать КП")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def approve_proposal_by_admin(tender_request: str):
    proposal = _get_latest_child("Commercial Proposal", tender_request)
    if not proposal:
        frappe.throw("Commercial Proposal не найден")
    updated = _apply_child_workflow_action(proposal, "КП на согласование")
    return {"name": updated.name, "status": updated.status}


@frappe.whitelist()
def send_to_client(tender_request: str):
    proposal = frappe.db.get_value(
        "Commercial Proposal",
        {"tender_request": tender_request, "status": "Admin Approved"},
        "name",
        order_by="creation desc",
    )
    if not proposal:
        frappe.throw("Сначала завершите админ-согласование Commercial Proposal (status = Admin Approved)")

    from designers.designers.doctype.commercial_proposal.commercial_proposal import send_to_client as send_proposal

    result = send_proposal(proposal)
    return {"proposal": result.get("proposal"), "status": result.get("status")}
