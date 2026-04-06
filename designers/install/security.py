from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import now
from frappe.utils.password import update_password

PASSWORD = "test"

BASE_ROLES = ["Biz User", "Biz Manager", "Biz Admin", "Integration User"]

ROLE_PROFILES = {
    "RP Accountant": ["Accounts User", "Biz User"],
    "RP Sales": ["Sales User", "Biz User"],
    "RP Purchase": ["Purchase User", "Biz User"],
    "RP Stock": ["Stock User", "Biz User"],
    "RP HR": ["HR User", "Biz User"],
    "RP Admin": ["System Manager", "Biz Admin", "Biz Manager", "Biz User"],
    "RP Integration": ["Integration User"],
}


@dataclass(frozen=True)
class DemoUser:
    login: str
    first_name: str
    last_name: str
    role_profile: str
    enabled: int = 1

    @property
    def email(self) -> str:
        return f"{self.last_name.lower()}@test.ru"


USERS = [
    DemoUser("accountant", "Nikita", "Orlov", "RP Accountant"),
    DemoUser("sales", "Ilya", "Sokolov", "RP Sales"),
    DemoUser("purchase", "Kirill", "Volkov", "RP Purchase"),
    DemoUser("stock", "Daniil", "Morozov", "RP Stock"),
    DemoUser("hr", "Lev", "Kuznetsov", "RP HR"),
    DemoUser("admin", "Artem", "Lebedev", "RP Admin"),
    DemoUser("integration", "Roman", "Egorov", "RP Integration"),
]


DOC_PERMISSIONS = {
    "Tender Request": {
        "Biz User": dict(read=1, write=1, create=1, submit=1, cancel=0, amend=0, delete=0),
        "Biz Manager": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=0, delete=0),
        "Biz Admin": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=1, delete=1),
        "Integration User": dict(read=1, write=1, create=1, submit=0, cancel=0, amend=0, delete=0),
    },
    "Tender Budget": {
        "Biz User": dict(read=1, write=1, create=1, submit=1, cancel=0, amend=0, delete=0),
        "Biz Manager": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=0, delete=0),
        "Biz Admin": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=1, delete=1),
        "Integration User": dict(read=1, write=0, create=0, submit=0, cancel=0, amend=0, delete=0),
    },
    "Commercial Proposal": {
        "Biz User": dict(read=1, write=1, create=1, submit=1, cancel=0, amend=0, delete=0),
        "Biz Manager": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=0, delete=0),
        "Biz Admin": dict(read=1, write=1, create=1, submit=1, cancel=1, amend=1, delete=1),
        "Integration User": dict(read=1, write=0, create=0, submit=0, cancel=0, amend=0, delete=0),
    },
}


WORKFLOWS = {
    "Tender Request Workflow": {
        "doctype": "Tender Request",
        "state_field": "status",
        "states": [
            ("New Request", "Biz User"),
            ("In Progress", "Biz User"),
            ("Under Review", "Biz Manager"),
            ("Rejected", "Biz Manager"),
            ("Cancelled", "Biz Manager", 2),
            ("Budget Drafting", "Biz User"),
            ("Budget Director Review", "Biz Manager"),
            ("Budget CEO Review", "Biz Admin"),
            ("Budget Approved", "Biz Admin"),
            ("Proposal Drafting", "Biz User"),
            ("Proposal Review", "Biz Manager"),
            ("Proposal Approved", "Biz Manager"),
            ("Sent to Client", "Biz User"),
            ("Archived", "Biz Manager", 1),
        ],
        "transitions": [
            ("New Request", "Принять в работу", "In Progress", "Biz User"),
            ("In Progress", "На согласование", "Under Review", "Biz User"),
            ("Under Review", "Отклонить", "Rejected", "Biz Manager"),
            ("Under Review", "Создать бюджет", "Budget Drafting", "Biz Manager"),
            ("Budget Drafting", "Отклонить", "Rejected", "Biz Manager"),
            ("Budget Director Review", "Отклонить", "Rejected", "Biz Manager"),
            ("Budget CEO Review", "Отклонить", "Rejected", "Biz Admin"),
            ("Proposal Drafting", "Отклонить", "Rejected", "Biz Manager"),
            ("Proposal Review", "Отклонить", "Rejected", "Biz Manager"),
            ("Proposal Approved", "Отклонить", "Rejected", "Biz Manager"),
            ("New Request", "В архив", "Archived", "Biz Manager"),
            ("In Progress", "В архив", "Archived", "Biz Manager"),
            ("Under Review", "В архив", "Archived", "Biz Manager"),
            ("Budget Drafting", "В архив", "Archived", "Biz Manager"),
            ("Budget Director Review", "В архив", "Archived", "Biz Manager"),
            ("Budget CEO Review", "В архив", "Archived", "Biz Admin"),
            ("Budget Approved", "В архив", "Archived", "Biz Admin"),
            ("Proposal Drafting", "В архив", "Archived", "Biz Manager"),
            ("Proposal Review", "В архив", "Archived", "Biz Manager"),
            ("Proposal Approved", "В архив", "Archived", "Biz Manager"),
            ("Sent to Client", "В архив", "Archived", "Biz Manager"),
            ("Rejected", "В архив", "Archived", "Biz Manager"),
            ("Archived", "Отменить КП", "Cancelled", "Biz Manager"),
        ],
    },
    "Tender Budget Workflow": {
        "doctype": "Tender Budget",
        "state_field": "status",
        "states": [
            ("Draft", "Biz User"),
            ("Under Director Review", "Biz Manager"),
            ("Under CEO Review", "Biz Admin"),
            ("Approved", "Biz Admin"),
            ("Rejected", "Biz Manager"),
            ("Cancelled", "Biz Manager", 2),
            ("Archived", "Biz Admin", 1),
        ],
        "transitions": [
            ("Draft", "Бюджет на согласование", "Under Director Review", "Biz User"),
            ("Under Director Review", "Согласовать бюджет", "Under CEO Review", "Biz Manager"),
            ("Under Director Review", "Отклонить бюджет", "Rejected", "Biz Manager"),
            ("Under CEO Review", "Согласовать бюджет", "Approved", "Biz Admin"),
            ("Under CEO Review", "Отклонить бюджет", "Rejected", "Biz Admin"),
            ("Draft", "Отправить в архив", "Archived", "Biz Manager"),
            ("Under Director Review", "Отправить в архив", "Archived", "Biz Manager"),
            ("Under CEO Review", "Отправить в архив", "Archived", "Biz Admin"),
            ("Approved", "Отправить в архив", "Archived", "Biz Admin"),
            ("Rejected", "Отправить в архив", "Archived", "Biz Admin"),
            ("Archived", "Cancel Budget", "Cancelled", "Biz Admin"),
        ],
    },
    "Commercial Proposal Workflow": {
        "doctype": "Commercial Proposal",
        "state_field": "status",
        "states": [
            ("Draft", "Biz User"),
            ("Under Approval", "Biz Manager"),
            ("Approved", "Biz Manager"),
            ("Admin Review", "Biz Admin"),
            ("Admin Approved", "Biz Admin"),
            ("Sent", "Biz User"),
            ("Rejected", "Biz Manager"),
            ("Cancelled", "Biz Manager", 2),
            ("Archived", "Biz Admin", 1),
        ],
        "transitions": [
            ("Draft", "КП на согласование", "Under Approval", "Biz User"),
            ("Under Approval", "Согласовать КП", "Approved", "Biz Manager"),
            ("Under Approval", "Отклонить КП", "Rejected", "Biz Manager"),
            ("Approved", "Согласовать КП", "Admin Review", "Biz Admin"),
            ("Admin Review", "КП на согласование", "Admin Approved", "Biz Admin"),
            ("Admin Review", "Отклонить КП", "Rejected", "Biz Admin"),
            ("Admin Approved", "Отправить КП клиенту", "Sent", "Biz Manager"),
            ("Draft", "В архив", "Archived", "Biz Manager"),
            ("Under Approval", "В архив", "Archived", "Biz Manager"),
            ("Approved", "В архив", "Archived", "Biz Manager"),
            ("Admin Review", "В архив", "Archived", "Biz Admin"),
            ("Admin Approved", "В архив", "Archived", "Biz Admin"),
            ("Sent", "В архив", "Archived", "Biz Admin"),
            ("Rejected", "В архив", "Archived", "Biz Manager"),
            ("Archived", "Cancel Proposal", "Cancelled", "Biz Admin"),
        ],
    },
}

LEGACY_WORKFLOWS = (
    "Tender Budget Approval Workflow",
    "Commercial Proposal Approval Workflow",
)


def apply_security_governance() -> None:
    ensure_roles()
    ensure_role_profiles()
    ensure_users()
    ensure_doc_permissions()
    ensure_user_permissions()
    ensure_workflow_states()
    ensure_workflows()
    validate_setup()


def ensure_roles() -> None:
    for role_name in BASE_ROLES:
        if frappe.db.exists("Role", role_name):
            continue
        frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)


def ensure_role_profiles() -> None:
    for profile_name, roles in ROLE_PROFILES.items():
        for role in roles:
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)

        if frappe.db.exists("Role Profile", profile_name):
            # Ensure newly added roles are present in an existing profile
            # without forcing full document update.
            _insert_role_profile_sql(profile_name, roles)
            continue

        profile = frappe.get_doc(
            {
                "doctype": "Role Profile",
                "role_profile": profile_name,
                "roles": [{"role": role} for role in roles],
            }
        )
        try:
            profile.insert(ignore_permissions=True)
        except frappe.DocumentLockedError:
            _insert_role_profile_sql(profile_name, roles)


def _insert_role_profile_sql(profile_name: str, roles: list[str]) -> None:
    if not frappe.db.exists("Role Profile", profile_name):
        ts = now()
        frappe.db.sql(
            """
            insert into `tabRole Profile`
            (`name`,`creation`,`modified`,`modified_by`,`owner`,`docstatus`,`idx`,`role_profile`)
            values (%s,%s,%s,%s,%s,0,0,%s)
            """,
            (profile_name, ts, ts, "Administrator", "Administrator", profile_name),
        )

    for idx, role in enumerate(roles, start=1):
        if frappe.db.exists(
            "Has Role",
            {
                "parenttype": "Role Profile",
                "parentfield": "roles",
                "parent": profile_name,
                "role": role,
            },
        ):
            continue
        frappe.db.sql(
            """
            insert into `tabHas Role`
            (`name`,`creation`,`modified`,`modified_by`,`owner`,`docstatus`,`idx`,`role`,`parent`,`parentfield`,`parenttype`)
            values (%s,%s,%s,%s,%s,0,%s,%s,%s,'roles','Role Profile')
            """,
            (frappe.generate_hash(length=10), now(), now(), "Administrator", "Administrator", idx, role, profile_name),
        )


def ensure_users() -> None:
    for item in USERS:
        existing = frappe.db.get_value("User", {"email": item.email}, "name")
        if existing:
            user = frappe.get_doc("User", existing)
        else:
            user = frappe.new_doc("User")
            user.email = item.email
            user.first_name = item.first_name
            user.last_name = item.last_name
            user.send_welcome_email = 0
            user.user_type = "System User"
            user.enabled = item.enabled
            user.insert(ignore_permissions=True)

        user.set("role_profiles", [])
        user.append("role_profiles", {"role_profile": item.role_profile})
        user.enabled = item.enabled
        user.save(ignore_permissions=True)

        update_password(item.email, PASSWORD)


def _upsert_custom_docperm(doctype: str, role: str, flags: dict[str, int]) -> None:
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
        fields=["name"],
        order_by="creation asc",
    )
    exists = rows[0].name if rows else None

    # Keep first row and remove duplicates, otherwise UI shows duplicated permissions.
    for duplicate in rows[1:]:
        frappe.delete_doc("Custom DocPerm", duplicate.name, ignore_permissions=True, force=1)

    payload = {
        "parent": doctype,
        "role": role,
        "permlevel": 0,
        "if_owner": 0,
        "select": int(flags.get("read", 0)),
        "read": int(flags.get("read", 0)),
        "write": int(flags.get("write", 0)),
        "create": int(flags.get("create", 0)),
        "submit": int(flags.get("submit", 0)),
        "cancel": int(flags.get("cancel", 0)),
        "amend": int(flags.get("amend", 0)),
        "delete": int(flags.get("delete", 0)),
        "report": int(flags.get("read", 0)),
        "export": int(flags.get("read", 0)),
        "import": 0,
        "share": 0,
        "print": int(flags.get("read", 0)),
        "email": int(flags.get("read", 0)),
    }

    if exists:
        doc = frappe.get_doc("Custom DocPerm", exists)
        doc.update(payload)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Custom DocPerm", **payload}).insert(ignore_permissions=True)


def ensure_doc_permissions() -> None:
    for doctype_name, role_map in DOC_PERMISSIONS.items():
        if not frappe.db.exists("DocType", doctype_name):
            continue

        for role_name, rights in role_map.items():
            _upsert_custom_docperm(doctype_name, role_name, rights)

        frappe.clear_cache(doctype=doctype_name)


def _add_user_permission(
    user: str,
    allow: str,
    value: str | None,
    *,
    applicable_for: str | None = None,
) -> None:
    if not value:
        return

    filters = {
        "user": user,
        "allow": allow,
        "for_value": value,
    }
    if frappe.db.exists("User Permission", filters):
        return

    payload = {
        "doctype": "User Permission",
        "user": user,
        "allow": allow,
        "for_value": value,
        "is_default": 1,
        "apply_to_all_doctypes": 0 if applicable_for else 1,
    }
    if applicable_for:
        payload["applicable_for"] = applicable_for

    frappe.get_doc(payload).insert(ignore_permissions=True)


def ensure_user_permissions() -> None:
    company = frappe.db.get_value("Company", {}, "name")
    warehouse = frappe.db.get_value("Warehouse", {}, "name")
    branch = frappe.db.get_value("Branch", {}, "name") if frappe.db.exists("DocType", "Branch") else None
    cost_center = frappe.db.get_value("Cost Center", {"is_group": 0}, "name")

    for item in USERS:
        if item.role_profile in {"RP Admin", "RP Integration"}:
            continue

        _add_user_permission(item.email, "Company", company)
        _add_user_permission(item.email, "Warehouse", warehouse, applicable_for="Stock Entry")
        _add_user_permission(item.email, "Cost Center", cost_center, applicable_for="Purchase Invoice")

        if branch:
            _add_user_permission(item.email, "Branch", branch)


def _ensure_workflow_actions(transitions: list[tuple[str, str, str, str]]) -> None:
    for _, action, _, _ in transitions:
        if frappe.db.exists("Workflow Action Master", action):
            continue
        frappe.get_doc(
            {
                "doctype": "Workflow Action Master",
                "workflow_action_name": action,
            }
        ).insert(ignore_permissions=True)


def ensure_workflow_states() -> None:
    states = set()
    for definition in WORKFLOWS.values():
        for state_def in definition["states"]:
            state_name = state_def[0]
            states.add(state_name)

    for state_name in states:
        if frappe.db.exists("Workflow State", state_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Workflow State",
                "workflow_state_name": state_name,
                "style": "Primary",
            }
        ).insert(ignore_permissions=True)


def _upsert_workflow(name: str, definition: dict) -> None:
    doctype_name = definition["doctype"]
    if not frappe.db.exists("DocType", doctype_name):
        return

    transitions = definition["transitions"]
    _ensure_workflow_actions(transitions)

    if frappe.db.exists("Workflow", name):
        wf = frappe.get_doc("Workflow", name)
        wf.states = []
        wf.transitions = []
    else:
        wf = frappe.new_doc("Workflow")
        wf.workflow_name = name

    wf.document_type = doctype_name
    wf.workflow_state_field = definition["state_field"]
    wf.is_active = 1
    wf.override_status = 1
    wf.send_email_alert = 0

    for state_def in definition["states"]:
        if len(state_def) == 3:
            state_name, allow_edit, doc_status = state_def
        else:
            state_name, allow_edit = state_def
            doc_status = 0
        wf.append(
            "states",
            {
                "state": state_name,
                "doc_status": doc_status,
                "allow_edit": allow_edit,
                "update_field": definition["state_field"],
                "update_value": state_name,
                "send_email": 0,
                "next_action_email_template": None,
            },
        )

    for state, action, next_state, allowed in transitions:
        wf.append(
            "transitions",
            {
                "state": state,
                "action": action,
                "next_state": next_state,
                "allowed": allowed,
                "allow_self_approval": 1,
            },
        )

    wf.flags.ignore_validate = True
    wf.save(ignore_permissions=True)


def ensure_workflows() -> None:
    for legacy_name in LEGACY_WORKFLOWS:
        if not frappe.db.exists("Workflow", legacy_name):
            continue
        try:
            frappe.delete_doc("Workflow", legacy_name, ignore_permissions=True, force=1)
        except Exception:
            frappe.db.set_value("Workflow", legacy_name, "is_active", 0, update_modified=False)

    for workflow_name, definition in WORKFLOWS.items():
        _upsert_workflow(workflow_name, definition)


def validate_setup() -> None:
    missing = []

    for item in USERS:
        if not frappe.db.exists("User", item.email):
            missing.append(f"User: {item.email}")
            continue

        user_doc = frappe.get_doc("User", item.email)
        assigned_profiles = {row.role_profile for row in (user_doc.role_profiles or [])}
        if item.role_profile not in assigned_profiles:
            missing.append(f"Role Profile mismatch: {item.email} -> {sorted(assigned_profiles)}")

    for workflow_name in WORKFLOWS:
        if not frappe.db.exists("Workflow", workflow_name):
            missing.append(f"Workflow: {workflow_name}")

    for doctype_name in DOC_PERMISSIONS:
        if not frappe.db.exists("DocType", doctype_name):
            continue
        if not frappe.db.exists("Custom DocPerm", {"parent": doctype_name, "role": "Biz User"}):
            missing.append(f"Custom DocPerm for {doctype_name}")

    if missing:
        frappe.throw(_("Security setup validation failed:\n{0}").format("\n".join(missing)))
