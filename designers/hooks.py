app_name = "designers"
app_title = "Designers"
app_publisher = "Dmitriy"
app_description = "Designers custom app"
app_email = "dmitriy@example.com"
app_license = "mit"

required_apps = ["frappe"]

app_include_js = ["/assets/designers/js/notification_badge.js"]
app_include_css = ["/assets/designers/css/notification_badge.css"]

doctype_js = {
	"Tender Request": "public/js/tender_request.js",
}

permission_query_conditions = {
	"Tender Request": "designers.permissions.tender_request.permission_query_conditions",
	"Tender Budget": "designers.permissions.tender_budget.permission_query_conditions",
	"Commercial Proposal": "designers.permissions.commercial_proposal.permission_query_conditions",
}

has_permission = {
	"Tender Request": "designers.permissions.tender_request.has_permission",
	"Tender Budget": "designers.permissions.tender_budget.has_permission",
	"Commercial Proposal": "designers.permissions.commercial_proposal.has_permission",
}

scheduler_events = {
	"daily": [
		"designers.tasks.check_deadlines",
	]
}

after_install = "designers.install.setup.after_install"
before_migrate = "designers.install.setup.before_migrate"
after_migrate = "designers.install.setup.after_migrate"

fixtures = [
	{
		"doctype": "Print Format",
		"filters": [["doc_type", "=", "Commercial Proposal"]],
	},
	{
		"doctype": "Notification",
		"filters": [["is_standard", "=", 0]],
	},
	{
		"doctype": "Workflow",
		"filters": [["name", "in", [
			"Tender Request Workflow",
			"Tender Budget Workflow",
			"Commercial Proposal Workflow",
		]]],
	},
	{
		"doctype": "Workflow State",
		"filters": [["workflow_state_name", "in", [
			"Draft",
			"Review 1 level",
			"Review 2 level",
			"Approved",
			"Rejected",
			"Cancelled",
			"Archived",
			"New Request",
			"In Progress",
			"Under Review",
			"Budget Drafting",
			"Budget Director Review",
			"Budget CEO Review",
			"Budget Approved",
			"Proposal Drafting",
			"Proposal Review",
			"Proposal Approved",
			"Sent to Client",
			"Under Director Review",
			"Under CEO Review",
			"Under Approval",
			"Admin Review",
			"Admin Approved",
			"Sent",
		]]],
	},
	{
		"doctype": "Workflow Action Master",
		"filters": [["workflow_action_name", "in", [
			"На согласование",
			"Согласовать",
			"Отклонить",
			"Арихивировать",
			"Вернуть в работу",
			"Отправить в архив",
			"Cancel Budget",
		]]],
	},
]

override_whitelisted_methods = {
	"frappe.handler.upload_file": "designers.upload.restricted_upload_file"
}

jinja = {
	"methods": [
		"designers.utils.print_format.loads_json",
	],
}
