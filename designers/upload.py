import frappe

ALLOWED_GUEST_DOCTYPES = {"Tender From Guest"}  # сюда нужные DocType

@frappe.whitelist(allow_guest=True, methods=["POST"])
def restricted_upload_file():
	doctype = frappe.form_dict.doctype

	if frappe.session.user == "Guest" and doctype not in ALLOWED_GUEST_DOCTYPES:
		frappe.throw("Guest upload is not allowed for this DocType", frappe.PermissionError)

	# передаем в стандартный обработчик
	from frappe.handler import upload_file as core_upload_file
	return core_upload_file()
