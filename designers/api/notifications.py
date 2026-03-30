import frappe
from designers.services.notification_service import notify_new_request


def notify_manager(doc, method=None):
    try:
        notify_new_request(doc)
    except Exception:
        # Do not block document creation when SMTP is missing or misconfigured.
        frappe.log_error(
            title="Notify manager failed",
            message=frappe.get_traceback(),
        )
