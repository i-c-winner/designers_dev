from __future__ import annotations

import frappe
from designers.permissions.common import (
    ALLOWED_CREATE_ROLES,
    can_manager_see_all,
    get_roles,
    is_super_user,
    user_has_tender_access,
)


def permission_query_conditions(user: str | None = None) -> str | None:
    user = user or frappe.session.user
    roles = get_roles(user)

    if is_super_user(user, roles) or can_manager_see_all(user, roles):
        return None

    user_escaped = frappe.db.escape(user)
    return (
        f"(`tabTender Request`.`owner` = {user_escaped} "
        f"or ifnull(`tabTender Request`.`assigned_to`, '') = {user_escaped} "
        "or exists ("
        "select 1 from `tabTender Request Access User` trau "
        "where trau.parent = `tabTender Request`.name "
        f"and trau.user = {user_escaped}"
        "))"
    )


def has_permission(doc, user: str | None = None, ptype: str | None = None) -> bool:
    user = user or frappe.session.user
    ptype = (ptype or "read").lower()
    roles = get_roles(user)

    if is_super_user(user, roles) or can_manager_see_all(user, roles):
        return True

    if ptype == "create":
        return bool(roles & ALLOWED_CREATE_ROLES) and user != "Guest"

    if ptype in {"read", "write", "submit", "cancel", "amend", "delete"}:
        return user_has_tender_access(user, doc.name)

    return False
