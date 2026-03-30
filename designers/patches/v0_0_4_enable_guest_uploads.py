import frappe


def execute():
    settings = frappe.get_single("System Settings")
    if not settings.allow_guests_to_upload_files:
        settings.allow_guests_to_upload_files = 1
        settings.save(ignore_permissions=True)
        frappe.db.commit()
