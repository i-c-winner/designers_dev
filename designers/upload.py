import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.file_manager import save_file

ALLOWED_GUEST_DOCTYPES = {"Tender From Guest", "Tender Request"}  # сюда нужные DocType

@frappe.whitelist(allow_guest=True, methods=["POST"])
def restricted_upload_file():
    doctype = frappe.form_dict.doctype

    if frappe.session.user == "Guest" and doctype not in ALLOWED_GUEST_DOCTYPES:
        frappe.throw("Guest upload is not allowed for this DocType", frappe.PermissionError)

    # For Guest + allowed web forms, bypass core doctype write checks and save file directly.
    if frappe.session.user == "Guest" and doctype in ALLOWED_GUEST_DOCTYPES and "file" in frappe.request.files:
        file = frappe.request.files["file"]
        content = file.stream.read()
        filename = file.filename

        if not filename:
            frappe.throw(_("Please select a file"))

        file_doc = save_file(
            fname=filename,
            content=content,
            dt=doctype,
            dn=frappe.form_dict.docname,
            folder=frappe.form_dict.folder or "Home",
            is_private=cint(frappe.form_dict.is_private),
            df=frappe.form_dict.fieldname,
        )

        return {
            "name": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
            "is_private": file_doc.is_private,
        }

    # передаем в стандартный обработчик
    from frappe.handler import upload_file as core_upload_file
    return core_upload_file()
