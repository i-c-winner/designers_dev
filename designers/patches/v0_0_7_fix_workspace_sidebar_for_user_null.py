from __future__ import annotations

import frappe


def execute():
    sidebar_name = "Designers"

    sidebar_id = frappe.db.exists("Workspace Sidebar", sidebar_name)
    if not sidebar_id:
        sidebar_id = frappe.db.get_value("Workspace Sidebar", {"title": sidebar_name}, "name")
    if not sidebar_id:
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_id)
    sidebar.for_user = None
    sidebar.save(ignore_permissions=True)
