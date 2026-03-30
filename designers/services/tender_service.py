from __future__ import annotations

from typing import Iterable

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as assign_add
from frappe.utils import now_datetime, today


WORKFLOW_STATUSES: tuple[str, ...] = (
    "New Request",
    "In Progress",
    "Under Review",
    "Rejected",
    "Budget Drafting",
    "Budget Director Review",
    "Budget CEO Review",
    "Budget Approved",
    "Proposal Drafting",
    "Proposal Review",
    "Proposal Approved",
    "Sent to Client",
)


def make_project_name(prefix: str | None, project_type: str | None) -> str:
    prefix = (prefix or "GEN").strip().upper()
    ptype = (project_type or "General").strip().replace(" ", "")
    stamp = now_datetime().strftime("%H%M%S")
    suffix = frappe.generate_hash(length=4).upper()
    return f"{today()}_{prefix}_{ptype}_{stamp}_{suffix}"


def create_project_structure(project_name: str, owner: str | None = None) -> None:
    """Create a dedicated file tree in File DocType for tender artifacts."""
    owner = owner or frappe.session.user
    root_name = project_name
    root_folder_id = frappe.db.get_value(
        "File",
        {"file_name": root_name, "is_folder": 1, "folder": "Home"},
        "name",
    )

    if not root_folder_id:
        root_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": root_name,
                "is_folder": 1,
                "folder": "Home",
                "owner": owner,
            }
        ).insert(ignore_permissions=True, ignore_if_duplicate=True)
        root_folder_id = root_doc.name

    for folder in ("01.InitiatedProject", "02.Budget", "03.Application form"):
        file_name = folder
        if frappe.db.exists("File", {"file_name": file_name, "folder": root_folder_id, "is_folder": 1}):
            continue

        frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "is_folder": 1,
                "folder": root_folder_id,
                "owner": owner,
            }
        ).insert(ignore_permissions=True, ignore_if_duplicate=True)


def find_user_by_roles(roles: Iterable[str]) -> str | None:
    roles = tuple(set(roles))
    if not roles:
        return None

    user = frappe.db.sql(
        """
        select distinct h.parent
        from `tabHas Role` h
        inner join `tabUser` u on u.name = h.parent
        where h.role in %(roles)s
          and ifnull(h.parenttype, 'User') = 'User'
          and h.parent not in ('Administrator', 'Guest')
          and ifnull(u.enabled, 0) = 1
        order by h.modified desc
        limit 1
        """,
        {"roles": roles},
        as_dict=True,
    )
    return user[0].parent if user else None


def assign_next_user(doc) -> None:
    status_to_roles = {
        "New Request": ("Sales Manager",),
        "In Progress": ("Sales Manager",),
        "Under Review": ("Design Director", "Sales Manager"),
        "Budget Director Review": ("Design Director",),
        "Budget CEO Review": ("CEO",),
        "Proposal Review": ("Design Director",),
    }

    roles = status_to_roles.get(doc.status)
    if not roles:
        return

    user = find_user_by_roles(roles)
    if not user:
        return

    if getattr(doc, "assigned_to", None) != user:
        doc.db_set("assigned_to", user, update_modified=False)

    if not frappe.db.exists(
        "ToDo",
        {
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "allocated_to": user,
            "status": ("!=", "Cancelled"),
        },
    ):
        assign_add(
            {
                "assign_to": [user],
                "doctype": doc.doctype,
                "name": doc.name,
                "description": _("Tender request requires your attention"),
                "date": now_datetime().date(),
            }
        )


def is_website_tender(doc) -> bool:
    return (doc.source or "").strip() == "Website"
