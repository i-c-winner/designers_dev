import frappe


@frappe.whitelist()
def get_notification_logs_live(limit: int = 20):
	"""Uncached notification feed for instant dropdown refresh."""
	limit = max(1, min(int(limit or 20), 200))

	notification_logs = frappe.db.get_list(
		"Notification Log",
		fields=["*"],
		filters={"for_user": frappe.session.user},
		limit=limit,
		order_by="creation desc",
	)

	users = sorted({log.from_user for log in notification_logs if log.get("from_user")})
	user_info = frappe._dict()

	for user in users:
		frappe.utils.add_user_info(user, user_info)

	return {"notification_logs": notification_logs, "user_info": user_info}
