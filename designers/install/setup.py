
from __future__ import annotations

import frappe

from designers.install.security import (
    ensure_doc_permissions,
    ensure_role_profiles,
    ensure_roles,
)

WEB_FORM_PHONE_CLIENT_SCRIPT = """
frappe.web_form.validate = () => {
    const phone = (frappe.web_form.get_value("contact_phone") || "").trim();
    const regex = /^\\+7-(?:\\d{3}|\\(\\d{3}\\))-\\d{3}-\\d{2}-\\d{2}$/;
    if (!phone || !regex.test(phone)) {
        frappe.msgprint("Формат телефона: +7-999-123-45-67 или +7-(999)-123-45-67");
        return false;
    }
    return true;
};
""".strip()


def after_install():
    ensure_security_workflows()


def before_migrate():
    # Keep only role prerequisites before schema sync.
    ensure_roles()


def after_migrate():
    ensure_security_workflows()


def ensure_security_workflows():
    ensure_roles()
    ensure_role_profiles()
    ensure_doc_permissions()
    ensure_designers_workspace()
    ensure_designers_workspace_sidebar()
    ensure_designers_desktop_icon()
    ensure_commercial_proposal_web_form()


def ensure_designers_workspace():
    workspace_name = "Designers"

    if frappe.db.exists("Workspace", workspace_name):
        ws = frappe.get_doc("Workspace", workspace_name)
    else:
        ws = frappe.new_doc("Workspace")
        ws.name = workspace_name

    ws.title = workspace_name
    ws.label = workspace_name
    ws.module = "Designers"
    ws.app = "designers"
    ws.icon = "folder-normal"
    ws.public = 1
    ws.is_hidden = 0
    ws.for_user = ""
    ws.parent_page = ""
    ws.content = (
        '[{"id":"designers_header","type":"header","data":{"text":"<span class=\\"h4\\"><b>Designers</b></span>","col":12}},'
        '{"id":"designers_shortcut_tender_request","type":"shortcut","data":{"shortcut_name":"Проект","col":4}},'
        '{"id":"designers_shortcut_tender_budget","type":"shortcut","data":{"shortcut_name":"Бюджет","col":4}},'
        '{"id":"designers_shortcut_commercial_proposal","type":"shortcut","data":{"shortcut_name":"Коммерческое предложение","col":4}},'
        '{"id":"designers_card_links","type":"card","data":{"card_name":"Ссылки","col":12}}]'
    )

    ws.set("links", [])
    ws.append("links", {"type": "Link", "label": "Проект", "link_type": "DocType", "link_to": "Tender Request"})
    ws.append("links", {"type": "Link", "label": "Бюджет", "link_type": "DocType", "link_to": "Tender Budget"})
    ws.append(
        "links",
        {
            "type": "Link",
            "label": "Коммерческое предложение",
            "link_type": "DocType",
            "link_to": "Commercial Proposal",
        },
    )

    ws.set("shortcuts", [])
    ws.append("shortcuts", {"type": "DocType", "label": "Проект", "link_to": "Tender Request", "doc_view": "List"})
    ws.append("shortcuts", {"type": "DocType", "label": "Бюджет", "link_to": "Tender Budget", "doc_view": "List"})
    ws.append(
        "shortcuts",
        {
            "type": "DocType",
            "label": "Коммерческое предложение",
            "link_to": "Commercial Proposal",
            "doc_view": "List",
        },
    )

    ws.flags.ignore_mandatory = True
    ws.save(ignore_permissions=True)


def ensure_designers_workspace_sidebar():
    sidebar_title = "Designers"

    if frappe.db.exists("Workspace Sidebar", sidebar_title):
        sidebar = frappe.get_doc("Workspace Sidebar", sidebar_title)
    elif frappe.db.exists("Workspace Sidebar", {"title": sidebar_title}):
        sidebar_name = frappe.db.get_value("Workspace Sidebar", {"title": sidebar_title}, "name")
        sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    else:
        sidebar = frappe.new_doc("Workspace Sidebar")
        sidebar.name = sidebar_title
        sidebar.title = sidebar_title

    sidebar.module = "Designers"
    sidebar.standard = 1
    sidebar.app = "designers"
    sidebar.for_user = None
    sidebar.header_icon = "folder-normal"

    sidebar.set("items", [])
    sidebar.append("items", {"label": "Home", "type": "Link", "link_type": "Workspace", "link_to": "Designers"})
    sidebar.append(
        "items",
        {"label": "Проект", "type": "Link", "link_type": "DocType", "link_to": "Tender Request"},
    )
    sidebar.append(
        "items",
        {"label": "Бюджет", "type": "Link", "link_type": "DocType", "link_to": "Tender Budget"},
    )
    sidebar.append(
        "items",
        {
            "label": "Коммерческое предложение",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Commercial Proposal",
        },
    )

    sidebar.flags.ignore_mandatory = True
    sidebar.save(ignore_permissions=True)


def ensure_designers_desktop_icon():
    icon_name = "Designers"

    if frappe.db.exists("Desktop Icon", icon_name):
        icon = frappe.get_doc("Desktop Icon", icon_name)
    elif frappe.db.exists("Desktop Icon", {"label": icon_name}):
        icon = frappe.get_doc("Desktop Icon", {"label": icon_name})
    else:
        icon = frappe.new_doc("Desktop Icon")
        icon.name = icon_name

    icon.label = "Designers"
    icon.link_type = "Workspace Sidebar"
    icon.link_to = "Designers"
    icon.app = "designers"
    icon.standard = 1
    icon.hidden = 0
    icon.icon = "folder-normal"
    icon.sidebar = "Designers"

    icon.flags.ignore_mandatory = True
    icon.save(ignore_permissions=True)


def ensure_commercial_proposal_web_form():
    web_form_name = frappe.db.get_value("Web Form", {"route": "commercial-proposal"}, "name")
    if web_form_name:
        web_form = frappe.get_doc("Web Form", web_form_name)
        changed = False
    else:
        web_form = frappe.new_doc("Web Form")
        web_form.title = "Commercial Proposal"
        web_form.route = "commercial-proposal"
        web_form.doc_type = "Tender Request"
        web_form.module = "Designers"
        web_form.is_standard = 0
        web_form.allow_edit = 0
        web_form.allow_delete = 0
        web_form.allow_comments = 0
        web_form.allow_print = 0
        web_form.allow_incomplete = 0
        web_form.show_list = 0
        web_form.show_sidebar = 0
        web_form.button_label = "Save"
        web_form.set("web_form_fields", [])
        web_form.append(
            "web_form_fields",
            {
                "fieldname": "connect_user",
                "fieldtype": "Data",
                "label": "Контактное лицо",
                "reqd": 1,
            },
        )
        web_form.append(
            "web_form_fields",
            {
                "fieldname": "contact_phone",
                "fieldtype": "Data",
                "label": "Контактный телефон",
                "reqd": 1,
            },
        )
        web_form.append(
            "web_form_fields",
            {
                "fieldname": "files",
                "fieldtype": "Attach",
                "label": "Файлы",
            },
        )
        changed = True

    target_values = {
        "published": 1,
        "allow_multiple": 1,
        "anonymous": 1,
        "login_required": 0,
        "apply_document_permissions": 0,
        "client_script": WEB_FORM_PHONE_CLIENT_SCRIPT,
    }

    for fieldname, target_value in target_values.items():
        if web_form.get(fieldname) != target_value:
            web_form.set(fieldname, target_value)
            changed = True

    if changed:
        web_form.save(ignore_permissions=True)
