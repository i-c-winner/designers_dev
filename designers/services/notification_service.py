from __future__ import annotations

import frappe
from frappe import _

DEFAULT_NOTIFY_EMAIL = "d-belousov@hotmail.com"
NOTIFY_ROLES = ("Biz Manager", "Sales Manager", "Design Director", "System Manager")


def get_default_notify_email() -> str:
    configured = (frappe.conf.get("designers_notify_email") or "").strip()
    # Keep predictable fallback for local/dev if no dedicated setting is provided.
    return configured or DEFAULT_NOTIFY_EMAIL


def get_manager_recipients() -> list[str]:
    users = frappe.db.sql(
        """
        select distinct u.email
        from `tabHas Role` hr
        inner join `tabUser` u on u.name = hr.parent
        where hr.role in %(roles)s
          and hr.parent not in ('Administrator', 'Guest')
          and ifnull(u.enabled, 0) = 1
          and ifnull(u.user_type, '') != 'Website User'
          and ifnull(u.email, '') != ''
        """,
        {"roles": NOTIFY_ROLES},
        as_dict=True,
    )
    recipients = [row.email for row in users if row.email]
    if not recipients:
        recipients = [get_default_notify_email()]
    return sorted(set(recipients))


def notify_new_request(doc) -> None:
    recipients = get_manager_recipients()
    frappe.sendmail(
        recipients=recipients,
        subject=_("New request: {0}").format(doc.name),
        message=_("A new request <b>{0}</b> was created from web form.").format(doc.name),
        reference_doctype=doc.doctype,
        reference_name=doc.name,
        now=False,
    )


def notify_status_change(doc) -> None:
    recipients = []

    if doc.assigned_to:
        recipients.append(doc.assigned_to)

    if doc.client:
        customer_email = frappe.db.get_value("Contact Email", {"parent": doc.client, "is_primary": 1}, "email_id")
        if customer_email:
            recipients.append(customer_email)

    if not recipients:
        return

    frappe.sendmail(
        recipients=list(set(recipients)),
        subject=_("Tender {0} status changed to {1}").format(doc.name, doc.status),
        message=_(
            "Tender Request <b>{0}</b> has moved to status <b>{1}</b>."
        ).format(doc.name, doc.status),
        now=False,
    )


def notify_new_website_request(doc) -> None:
    frappe.sendmail(
        recipients=get_manager_recipients(),
        subject=_("New tender request from website: {0}").format(doc.name),
        message=_("Please review new website tender request <b>{0}</b>.").format(doc.name),
        reference_doctype=doc.doctype,
        reference_name=doc.name,
        now=False,
    )
