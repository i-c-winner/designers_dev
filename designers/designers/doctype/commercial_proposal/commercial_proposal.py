from __future__ import annotations

import hmac
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import frappe
import requests
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import add_to_date, get_datetime_str
from frappe.utils.file_manager import get_file, save_file
from frappe.utils import now_datetime


class CommercialProposal(Document):
    PARENT_STATUS_BY_PROPOSAL_STATUS = {
        "Draft": "Proposal Drafting",
        "Under Approval": "Proposal Review",
        "Approved": "Proposal Review",
        "Admin Review": "Proposal Review",
        "Admin Approved": "Proposal Approved",
        "Sent": "Sent to Client",
        "Rejected": "Rejected",
        "Cancelled": "Proposal Drafting",
    }

    def _archive_previous_versions(self):
        if not self.tender_request or not self.name:
            return

        for attempt in range(3):
            try:
                frappe.db.sql(
                    """
                    update `tabCommercial Proposal`
                    set status = 'Archived'
                    where tender_request = %s
                      and name != %s
                      and status != 'Archived'
                    """,
                    (self.tender_request, self.name),
                )
                return
            except frappe.QueryDeadlockError:
                if attempt == 2:
                    raise
                time.sleep(0.2)

    def validate(self):
        # Keep compatibility with sites where these fields were removed from DocType.
        if self.meta.has_field("tender_budget"):
            tender_budget = self.get("tender_budget")
            if tender_budget and self.meta.has_field("budget_version"):
                self.budget_version = frappe.db.get_value("Tender Budget", tender_budget, "version")

        if not self.tender_request:
            return

        latest_version = frappe.db.sql(
            """
            select coalesce(max(version), 0)
            from `tabCommercial Proposal`
            where tender_request = %s
            """,
            (self.tender_request,),
        )[0][0]

        if self.version and int(self.version) < int(latest_version):
            self.status = "Archived"

    def before_insert(self):
        if not self.tender_request:
            frappe.throw("Tender Request is required")

        self.flags.previous_latest_proposal = frappe.db.get_value(
            "Commercial Proposal",
            {"tender_request": self.tender_request},
            "name",
            order_by="version desc",
        )
        max_version = frappe.db.sql(
            """
            select coalesce(max(version), 0)
            from `tabCommercial Proposal`
            where tender_request = %s
            """,
            (self.tender_request,),
        )[0][0]
        self.version = int(max_version) + 1

    def after_insert(self):
        previous_latest = self.flags.get("previous_latest_proposal")
        if previous_latest:
            frappe.db.set_value("Commercial Proposal", previous_latest, "status", "Archived", update_modified=False)
        self._archive_previous_versions()

    def on_update(self):
        if not self.tender_request:
            return

        if self.tender_request and self.version:
            latest_version = frappe.db.sql(
                """
                select coalesce(max(version), 0)
                from `tabCommercial Proposal`
                where tender_request = %s
                """,
                (self.tender_request,),
            )[0][0]
            if int(self.version) < int(latest_version) and self.status != "Archived":
                self.db_set("status", "Archived", update_modified=False)
            elif int(self.version) == int(latest_version):
                self._archive_previous_versions()

        parent_status = self.PARENT_STATUS_BY_PROPOSAL_STATUS.get(self.status)
        frappe.db.set_value("Tender Request", self.tender_request, "commercial_proposal", self.name, update_modified=False)
        if parent_status:
            frappe.db.set_value("Tender Request", self.tender_request, "status", parent_status, update_modified=False)

        # Ensure workflow transition to "Sent" actually sends email with attachments.
        if self.status == "Sent" and not int(self.get("sent_to_client") or 0):
            self.db_set("sent_to_client", 1, update_modified=False)
            self.db_set("sent_on", now_datetime(), update_modified=False)


def _get_selected_client_attachment_docnames(proposal: CommercialProposal) -> list[str]:
    raw_value = proposal.get("client_send_attachments_json") or "[]"
    try:
        parsed = json.loads(raw_value)
    except Exception:
        parsed = []

    if not isinstance(parsed, list):
        return []

    deduped: list[str] = []
    seen = set()
    for value in parsed:
        candidate = str(value or "").strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _get_primary_customer_email(customer_name: str | None) -> str | None:
    if not customer_name:
        return None

    customer_contacts = frappe.db.sql(
        """
        select ce.email_id
        from `tabContact Email` ce
        inner join `tabDynamic Link` dl on dl.parent = ce.parent and dl.parenttype = 'Contact'
        where dl.link_doctype = 'Customer'
          and dl.link_name = %s
          and ifnull(ce.is_primary, 0) = 1
        limit 1
        """,
        (customer_name,),
        as_dict=True,
    )
    if not customer_contacts:
        return None
    return customer_contacts[0].email_id


def _build_client_email_attachments(proposal: CommercialProposal) -> tuple[list[dict], list[str]]:
    attachments: list[dict] = []
    preselected: list[str] = []

    selected_extra = _get_selected_client_attachment_docnames(proposal)
    if selected_extra:
        rows = frappe.get_all(
            "File",
            filters={
                "name": ["in", selected_extra],
                "attached_to_doctype": "Commercial Proposal",
                "attached_to_name": proposal.name,
            },
            fields=["name", "file_name", "file_url"],
        )
        by_name = {row.name: row for row in rows}
        for docname in selected_extra:
            row = by_name.get(docname)
            if not row:
                continue
            attachments.append(
                {
                    "name": row.name,
                    "file_name": row.file_name or row.file_url or row.name,
                    "file_url": row.file_url,
                }
            )
            preselected.append(row.name)

    # Deduplicate by File docname, preserving order.
    deduped: list[dict] = []
    seen = set()
    for item in attachments:
        key = item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    preselected = [name for name in preselected if name in seen]
    return deduped, preselected


def _build_print_format_attachment(proposal: CommercialProposal) -> dict:
    pdf_bytes = frappe.get_print(
        "Commercial Proposal",
        proposal.name,
        print_format="Commercial Proposal",
        as_pdf=True,
    )
    return {
        "fname": f"{proposal.name}.pdf",
        "fcontent": pdf_bytes,
    }


def _assert_client_email_sender_role() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if "Biz Manager" not in roles and frappe.session.user != "Administrator":
        frappe.throw("Only Biz Manager can send proposal email to client", frappe.PermissionError)


@frappe.whitelist()
def send_to_client(proposal_name: str):
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    tender = frappe.get_doc("Tender Request", proposal.tender_request)

    # Apply workflow transition instead of forcing status assignment.
    # Direct assignment can fail with "Workflow State transition not allowed".
    proposal = apply_workflow(proposal, "Отправить КП клиенту")
    proposal.reload()

    # Keep parent status in sync without invoking another workflow transition.
    if tender.status != "Sent to Client":
        frappe.db.set_value("Tender Request", tender.name, "status", "Sent to Client", update_modified=False)

    return {"proposal": proposal.name, "status": proposal.status}


@frappe.whitelist()
def resend_to_client(proposal_name: str):
    frappe.throw("Automatic resend is disabled. Please use the email composer in UI.")


@frappe.whitelist()
def get_client_email_context(proposal_name: str) -> dict:
    _assert_client_email_sender_role()

    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="read", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    tender = frappe.get_doc("Tender Request", proposal.tender_request)
    recipient = _get_primary_customer_email(tender.client)
    if not recipient:
        frappe.throw("Primary customer email is required")

    attachments, preselected = _build_client_email_attachments(proposal)

    return {
        "recipients": [recipient],
        "subject": f"Commercial Proposal: {proposal.name}",
        "message": f"Your commercial proposal for tender {tender.name} is ready.",
        "attachments": attachments,
        "preselected_attachment_names": preselected,
    }


@frappe.whitelist()
def send_client_email_from_ui(
    proposal_name: str,
    recipients=None,
    subject: str | None = None,
    message: str | None = None,
) -> dict:
    _assert_client_email_sender_role()

    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="read", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    recipient_list: list[str]
    if isinstance(recipients, str):
        parts = recipients.replace(";", ",").split(",")
        recipient_list = [p.strip() for p in parts if p.strip()]
    elif isinstance(recipients, (list, tuple)):
        recipient_list = [str(p).strip() for p in recipients if str(p).strip()]
    else:
        recipient_list = []

    if not recipient_list:
        frappe.throw("At least one recipient email is required")

    attachments, _preselected = _build_client_email_attachments(proposal)
    file_attachments = [_build_print_format_attachment(proposal)]
    file_attachments.extend({"fid": row["name"]} for row in attachments if row.get("name"))

    frappe.sendmail(
        recipients=recipient_list,
        subject=(subject or f"Commercial Proposal: {proposal.name}"),
        message=(message or ""),
        attachments=file_attachments,
        reference_doctype="Commercial Proposal",
        reference_name=proposal.name,
        now=True,
    )

    if not int(proposal.get("sent_to_client") or 0):
        proposal.db_set("sent_to_client", 1, update_modified=False)
        proposal.db_set("sent_on", now_datetime(), update_modified=False)

    return {"ok": True, "attachments_count": len(file_attachments)}


@frappe.whitelist()
def get_client_send_attachments(proposal_name: str) -> dict:
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="read", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    selected = set(_get_selected_client_attachment_docnames(proposal))
    proposal_file_url = proposal.get("proposal_file")
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Commercial Proposal",
            "attached_to_name": proposal.name,
        },
        fields=["name", "file_name", "file_url", "modified"],
        order_by="modified desc",
    )

    return {
        "files": [
            {
                "name": row.name,
                "file_name": row.file_name,
                "file_url": row.file_url,
                "selected": row.name in selected,
            }
            for row in files
            if not (proposal_file_url and row.file_url == proposal_file_url)
        ]
    }


@frappe.whitelist()
def set_client_send_attachments(proposal_name: str, selected_file_docnames=None) -> dict:
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="write", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    if isinstance(selected_file_docnames, str):
        try:
            selected_file_docnames = json.loads(selected_file_docnames)
        except Exception:
            selected_file_docnames = []
    if not isinstance(selected_file_docnames, list):
        selected_file_docnames = []

    selected_names = []
    seen = set()
    for value in selected_file_docnames:
        docname = str(value or "").strip()
        if docname and docname not in seen:
            seen.add(docname)
            selected_names.append(docname)

    if selected_names:
        rows = frappe.get_all(
            "File",
            filters={
                "name": ["in", selected_names],
                "attached_to_doctype": "Commercial Proposal",
                "attached_to_name": proposal.name,
            },
            fields=["name", "file_url"],
        )
        proposal_file_url = proposal.get("proposal_file")
        valid_names = {
            row.name for row in rows if not (proposal_file_url and row.file_url == proposal_file_url)
        }
        selected_names = [name for name in selected_names if name in valid_names]

    proposal.db_set("client_send_attachments_json", json.dumps(selected_names), update_modified=False)
    return {"selected_count": len(selected_names)}


@frappe.whitelist()
def attach_proposal_docx(proposal_name: str, file_url: str) -> dict:
    if not proposal_name:
        frappe.throw("Commercial Proposal is required")
    if not file_url:
        frappe.throw("DOCX file is required")

    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="write", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    ext = Path((file_url or "").split("?", 1)[0]).suffix.lower()
    if ext != ".docx":
        frappe.throw("Only .docx files are allowed")

    source_file_name, content = get_file(file_url)
    if isinstance(content, str):
        content = content.encode()

    target_name = _normalize_docx_name(_resolve_file_name_by_url(file_url) or source_file_name)
    _delete_current_proposal_attachment(proposal)

    saved = save_file(
        fname=target_name,
        content=content,
        dt="Commercial Proposal",
        dn=proposal.name,
        is_private=1,
        df="proposal_file",
    )
    _set_file_name_for_url(saved.file_url, target_name)
    proposal.db_set("proposal_file", saved.file_url, update_modified=False)

    return {"file_url": saved.file_url, "file_name": saved.file_name}


def _get_onlyoffice_secret() -> str:
    secret = frappe.conf.get("onlyoffice_callback_secret") or frappe.conf.get("encryption_key")
    if not secret:
        frappe.throw("OnlyOffice secret is not configured")
    return str(secret)


def _sign_onlyoffice_payload(payload: str) -> str:
    secret = _get_onlyoffice_secret().encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


def _build_signed_query(proposal_name: str, file_url: str, expires_on: str) -> str:
    payload = f"{proposal_name}|{file_url}|{expires_on}"
    signature = _sign_onlyoffice_payload(payload)
    return urlencode(
        {
            "proposal_name": proposal_name,
            "file_url": file_url,
            "exp": expires_on,
            "sig": signature,
        }
    )


def _verify_signed_query(proposal_name: str, file_url: str, expires_on: str, signature: str) -> None:
    if not proposal_name or not file_url or not expires_on or not signature:
        frappe.throw("Invalid OnlyOffice signature")

    now_ts = now_datetime()
    exp_dt = frappe.utils.get_datetime(expires_on)
    if not exp_dt or now_ts > exp_dt:
        frappe.throw("OnlyOffice link is expired")

    payload = f"{proposal_name}|{file_url}|{expires_on}"
    expected = _sign_onlyoffice_payload(payload)
    if not hmac.compare_digest(expected, signature):
        frappe.throw("OnlyOffice signature mismatch")


def _ensure_docx_file(proposal: CommercialProposal) -> str:
    file_url = proposal.get("proposal_file") or ""
    if not file_url:
        frappe.throw("Upload DOCX file first")

    if Path(file_url.split("?", 1)[0]).suffix.lower() != ".docx":
        frappe.throw("Only .docx is supported for OnlyOffice editing")

    return file_url


def _normalize_docx_name(file_name: str | None) -> str:
    candidate = Path((file_name or "").strip()).name
    if not candidate:
        return "document.docx"
    if Path(candidate).suffix.lower() != ".docx":
        return f"{candidate}.docx"
    return candidate


def _resolve_file_name_by_url(file_url: str | None) -> str:
    if not file_url:
        return ""
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "file_name")
    if file_name:
        return str(file_name)
    return Path(str(file_url).split("?", 1)[0]).name


def _set_file_name_for_url(file_url: str, target_name: str) -> None:
    if not file_url or not target_name:
        return
    file_docnames = frappe.get_all("File", filters={"file_url": file_url}, pluck="name")
    for file_docname in file_docnames:
        try:
            frappe.db.set_value("File", file_docname, "file_name", target_name, update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to set file_name for {file_docname}")


def _rewrite_onlyoffice_download_url(download_url: str) -> str:
    if not download_url:
        return download_url

    parsed = urlparse(download_url)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        return download_url

    internal_server = (frappe.conf.get("onlyoffice_document_server_internal_url") or "http://onlyoffice").rstrip("/")
    internal_parsed = urlparse(internal_server)
    internal_scheme = internal_parsed.scheme or "http"
    internal_netloc = internal_parsed.netloc or internal_parsed.path
    if not internal_netloc:
        return download_url

    return urlunparse(
        (
            internal_scheme,
            internal_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _resolve_onlyoffice_server_url_for_backend() -> str:
    internal_server = (frappe.conf.get("onlyoffice_document_server_internal_url") or "").rstrip("/")
    configured_server = (frappe.conf.get("onlyoffice_document_server_url") or "").rstrip("/")

    if not configured_server:
        return internal_server

    parsed = urlparse(configured_server)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        if internal_server:
            return internal_server
        return "http://onlyoffice"

    return configured_server


def _delete_current_proposal_attachment(proposal: CommercialProposal) -> None:
    current_file_url = proposal.get("proposal_file")
    if not current_file_url:
        return

    file_docnames = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Commercial Proposal",
            "attached_to_name": proposal.name,
            "file_url": current_file_url,
        },
        pluck="name",
    )

    for file_docname in file_docnames:
        try:
            frappe.delete_doc("File", file_docname, ignore_permissions=True, force=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to delete previous proposal file {file_docname}")

    proposal.db_set("proposal_file", None, update_modified=False)


@frappe.whitelist()
def get_onlyoffice_editor_config(proposal_name: str) -> dict:
    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not frappe.has_permission("Commercial Proposal", ptype="write", doc=proposal):
        frappe.throw("Not permitted", frappe.PermissionError)

    document_server = (frappe.conf.get("onlyoffice_document_server_url") or "").rstrip("/")
    public_url = (frappe.conf.get("onlyoffice_public_url") or frappe.utils.get_url()).rstrip("/")
    internal_url = (frappe.conf.get("onlyoffice_internal_url") or public_url).rstrip("/")
    if not document_server:
        frappe.throw("Set onlyoffice_document_server_url in site_config.json")
    if not public_url:
        frappe.throw("Set onlyoffice_public_url in site_config.json")

    file_url = _ensure_docx_file(proposal)
    current_file_name = _normalize_docx_name(_resolve_file_name_by_url(file_url))
    expires_on = get_datetime_str(add_to_date(now_datetime(), minutes=30, as_datetime=True))
    signed_query = _build_signed_query(proposal.name, file_url, expires_on)

    doc_download_url = (
        f"{internal_url}/api/method/designers.designers.doctype.commercial_proposal.commercial_proposal.download_proposal_docx"
        f"?{signed_query}"
    )
    callback_url = (
        f"{internal_url}/api/method/designers.designers.doctype.commercial_proposal.commercial_proposal.onlyoffice_callback"
        f"?{signed_query}"
    )

    jwt_secret = frappe.conf.get("onlyoffice_jwt_secret")
    token_payload = None
    if jwt_secret:
        token_payload = {
            "document": {
                "fileType": "docx",
                "key": f"{proposal.name}-{frappe.generate_hash(length=10)}",
                "title": current_file_name,
                "url": doc_download_url,
                "permissions": {
                    "edit": True,
                    "download": True,
                    "print": True,
                    "copy": True,
                    "review": True,
                },
            },
            "editorConfig": {
                "callbackUrl": callback_url,
                "mode": "edit",
                "lang": (frappe.local.lang or "en"),
                "customization": {
                    "forcesave": True,
                },
                "user": {
                    "id": frappe.session.user,
                    "name": frappe.session.user_fullname or frappe.session.user,
                },
            },
            "documentType": "word",
        }
        try:
            import jwt  # pyjwt

            token = jwt.encode(token_payload, str(jwt_secret), algorithm="HS256")
        except Exception:
            frappe.throw("Install pyjwt for OnlyOffice JWT mode or unset onlyoffice_jwt_secret")
    else:
        token = None

    config = token_payload or {
        "document": {
            "fileType": "docx",
            "key": f"{proposal.name}-{frappe.generate_hash(length=10)}",
            "title": current_file_name,
            "url": doc_download_url,
            "permissions": {
                "edit": True,
                "download": True,
                "print": True,
                "copy": True,
                "review": True,
            },
        },
        "editorConfig": {
            "callbackUrl": callback_url,
            "mode": "edit",
            "lang": (frappe.local.lang or "en"),
            "customization": {
                "forcesave": True,
            },
            "user": {
                "id": frappe.session.user,
                "name": frappe.session.user_fullname or frappe.session.user,
            },
        },
        "documentType": "word",
    }
    if token:
        config["token"] = token

    return {
        "document_server_url": document_server,
        "config": config,
    }


@frappe.whitelist(allow_guest=True, methods=["GET", "HEAD"])
def download_proposal_docx(proposal_name: str, file_url: str, exp: str, sig: str):
    _verify_signed_query(proposal_name, file_url, exp, sig)

    _proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    file_name, content = get_file(file_url)
    if isinstance(content, str):
        content = content.encode()

    frappe.local.response.filename = file_name or _normalize_docx_name(_resolve_file_name_by_url(file_url))
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def onlyoffice_callback(
    proposal_name: str | None = None,
    file_url: str | None = None,
    exp: str | None = None,
    sig: str | None = None,
):
    def _oo_response(error_code: int):
        frappe.local.response.clear()
        frappe.local.response["error"] = int(error_code)
        frappe.local.response["http_status_code"] = 200
        return None

    payload = frappe.request.get_json(silent=True) or {}
    status = int(payload.get("status") or 0)
    if status not in {2, 6, 7}:
        return _oo_response(0)

    if status == 7:
        return _oo_response(0)

    # Some OnlyOffice builds post callback data without preserving callbackUrl query args.
    # In that case derive the proposal name from document key: "<proposal_name>-<random_hash>".
    if not proposal_name:
        callback_key = str(payload.get("key") or "")
        if callback_key and "-" in callback_key:
            proposal_name = callback_key.rsplit("-", 1)[0]

    if not proposal_name:
        frappe.log_error(frappe.as_json(payload), "OnlyOffice callback missing proposal_name")
        return _oo_response(0)

    proposal = frappe.get_doc("Commercial Proposal", proposal_name)
    if not file_url:
        file_url = proposal.get("proposal_file")
    if not file_url:
        frappe.log_error(frappe.as_json(payload), f"OnlyOffice callback missing file for {proposal_name}")
        return _oo_response(0)

    # Keep signed-query verification when args are present.
    if exp and sig:
        _verify_signed_query(proposal_name, file_url, exp, sig)

    download_url = _rewrite_onlyoffice_download_url(str(payload.get("url") or ""))
    if not download_url:
        return _oo_response(0)

    headers = {}
    jwt_secret = frappe.conf.get("onlyoffice_jwt_secret")
    if jwt_secret:
        try:
            import jwt  # pyjwt

            headers["Authorization"] = f"Bearer {jwt.encode({'url': download_url}, str(jwt_secret), algorithm='HS256')}"
        except Exception:
            pass

    try:
        response = requests.get(download_url, timeout=60, headers=headers)
        response.raise_for_status()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"OnlyOffice callback download failed for {proposal_name}")
        return _oo_response(1)

    target_name = _normalize_docx_name(_resolve_file_name_by_url(proposal.get("proposal_file")))
    _delete_current_proposal_attachment(proposal)

    saved = save_file(
        fname=target_name,
        content=response.content,
        dt="Commercial Proposal",
        dn=proposal.name,
        is_private=1,
        df="proposal_file",
    )
    _set_file_name_for_url(saved.file_url, target_name)
    proposal.db_set("proposal_file", saved.file_url, update_modified=False)

    return _oo_response(0)
