from __future__ import annotations

import frappe
from designers.permissions.common import (
    ALLOWED_CREATE_ROLES,
    can_manager_see_all,
    get_roles,
    is_super_user,
    user_has_tender_access,
)


def _owned_tender_condition(user: str) -> str:
    user_escaped = frappe.db.escape(user)
    return (
        "exists ("
        "select 1 from `tabTender Request` tr "
        "where tr.name = `tabTender Budget`.tender_request "
        f"and (tr.owner = {user_escaped} or ifnull(tr.assigned_to, '') = {user_escaped} "
        "or exists ("
        "select 1 from `tabTender Request Access User` trau "
        "where trau.parent = tr.name "
        f"and trau.user = {user_escaped}"
        "))"
        ")"
    )


def _can_access_tender(user: str, tender_request: str | None) -> bool:
    return user_has_tender_access(user, tender_request)


def permission_query_conditions(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    roles = get_roles(user)

    if is_super_user(user, roles) or can_manager_see_all(user, roles):
        return None

    return _owned_tender_condition(user)


def has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
    user = user or frappe.session.user
    ptype = (ptype or "read").lower()
    roles = get_roles(user)

    if is_super_user(user, roles) or can_manager_see_all(user, roles):
        return True

    if ptype == "create":
        return bool(roles & ALLOWED_CREATE_ROLES) and user != "Guest"

    if ptype == "write" and getattr(doc, "__islocal", 0):
        return bool(roles & ALLOWED_CREATE_ROLES) and user != "Guest"

    if ptype in {"read", "write", "submit", "cancel", "amend", "delete"}:
        return _can_access_tender(user, doc.get("tender_request"))

    return False
