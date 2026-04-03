from __future__ import annotations

from typing import Final

import frappe

ADMIN_ROLES: Final[set[str]] = {"System Manager", "Biz Admin"}
MANAGER_ROLES: Final[set[str]] = {"Biz Manager"}
ALLOWED_CREATE_ROLES: Final[set[str]] = {
    "Biz User",
    "Biz Manager",
    "Biz Admin",
    "Integration User",
}


def get_roles(user: str) -> set[str]:
    return set(frappe.get_roles(user))


def is_super_user(user: str, roles: set[str]) -> bool:
    return user == "Administrator" or bool(roles & ADMIN_ROLES)


def can_manager_see_all(user: str, roles: set[str]) -> bool:
    return False


def user_has_tender_access(user: str, tender_request: str | None) -> bool:
    if not tender_request:
        return False
    return bool(
        frappe.db.sql(
            """
            select 1
            from `tabTender Request` tr
            where tr.name = %s
              and (
                    tr.owner = %s
                    or ifnull(tr.assigned_to, '') = %s
                    or exists (
                        select 1
                        from `tabTender Request Access User` trau
                        where trau.parent = tr.name
                          and trau.user = %s
                    )
              )
            limit 1
            """,
            (tender_request, user, user, user),
        )
    )
