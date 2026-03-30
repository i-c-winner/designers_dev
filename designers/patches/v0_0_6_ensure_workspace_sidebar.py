from __future__ import annotations

import frappe


def _get_or_create_sidebar() -> "frappe.model.document.Document":
    sidebar_name = "Designers"

    if frappe.db.exists("Workspace Sidebar", sidebar_name):
        return frappe.get_doc("Workspace Sidebar", sidebar_name)

    by_title = frappe.get_all(
        "Workspace Sidebar",
        filters={"title": sidebar_name},
        fields=["name"],
        limit=1,
    )
    if by_title:
        return frappe.get_doc("Workspace Sidebar", by_title[0].name)

    sidebar = frappe.new_doc("Workspace Sidebar")
    sidebar.title = sidebar_name
    sidebar.name = sidebar_name
    return sidebar


def execute():
    sidebar = _get_or_create_sidebar()
    sidebar.title = "Designers"
    sidebar.module = "Designers"
    sidebar.for_user = None
    sidebar.header_icon = "folder-normal"
    sidebar.standard = 0
    sidebar.app = "designers"

    sidebar.set("items", [])
    sidebar.append("items", {"label": "Home", "type": "Link", "link_type": "Workspace", "link_to": "Designers"})
    sidebar.append(
        "items",
        {"label": "Tender Request", "type": "Link", "link_type": "DocType", "link_to": "Tender Request"},
    )
    sidebar.append(
        "items",
        {"label": "Tender Budget", "type": "Link", "link_type": "DocType", "link_to": "Tender Budget"},
    )
    sidebar.append(
        "items",
        {
            "label": "Commercial Proposal",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Commercial Proposal",
        },
    )

    sidebar.flags.ignore_mandatory = True
    sidebar.save(ignore_permissions=True)
