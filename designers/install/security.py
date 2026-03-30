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
    "RP Admin": ["System Manager", "Biz Admin"],
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
            ("Budget Drafting", "Biz User"),
            ("Budget Director Review", "Biz Manager"),
            ("Budget CEO Review", "Biz Admin"),
            ("Budget Approved", "Biz Admin"),
            ("Proposal Drafting", "Biz User"),
            ("Proposal Review", "Biz Manager"),
            ("Proposal Approved", "Biz Admin"),
            ("Sent to Client", "Biz User"),
        ],
        "transitions": [
            ("New Request", "Start Work", "In Progress", "Biz User"),
            ("In Progress", "Send For Review", "Under Review", "Biz User"),
            ("Under Review", "Reject Request", "Rejected", "Biz Manager"),
            ("Under Review", "Start Budget", "Budget Drafting", "Biz Manager"),
            ("Budget Drafting", "Send To Director", "Budget Director Review", "Biz User"),
            ("Budget Director Review", "Approve Director", "Budget CEO Review", "Biz Manager"),
            ("Budget Director Review", "Reject Director", "Rejected", "Biz Manager"),
            ("Budget CEO Review", "Approve Budget", "Budget Approved", "Biz Admin"),
            ("Budget CEO Review", "Reject By CEO", "Rejected", "Biz Admin"),
            ("Budget Approved", "Start Proposal", "Proposal Drafting", "Biz User"),
            ("Proposal Drafting", "Submit Proposal", "Proposal Review", "Biz User"),
            ("Proposal Review", "Approve Proposal", "Proposal Approved", "Biz Manager"),
            ("Proposal Review", "Reject Proposal", "Rejected", "Biz Manager"),
            ("Proposal Approved", "Send To Client", "Sent to Client", "Biz User"),
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
            # Avoid touching existing profiles during migrate to prevent lock/contention
            # from queued update_all_users jobs.
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
    exists = frappe.db.get_value(
        "Custom DocPerm",
        {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
        "name",
    )

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
        for state_name, _ in definition["states"]:
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

    for state_name, allow_edit in definition["states"]:
        wf.append(
            "states",
            {
                "state": state_name,
                "doc_status": 0,
                "allow_edit": allow_edit,
                "update_field": definition["state_field"],
                "update_value": state_name,
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
    # Variant 1: single source workflow lives on Tender Request.
    # Child DocTypes (Tender Budget / Commercial Proposal) should not carry separate approval workflows.
    for legacy_name in LEGACY_WORKFLOWS:
        if not frappe.db.exists("Workflow", legacy_name):
            continue
        try:
            frappe.delete_doc("Workflow", legacy_name, ignore_permissions=True, force=1)
        except Exception:
            # Fallback: keep record but disable it so it never controls transitions.
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
