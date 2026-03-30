app_name = "designers"
app_title = "Designers"
app_publisher = "Dmitriy"
app_description = "Designers custom app"
app_email = "dmitriy@example.com"
app_license = "mit"

required_apps = ["frappe"]

doctype_js = {
    "Tender Request": "public/js/tender_request.js",
}

doc_events = {
    "Tender From Guest": {
        "after_insert": "designers.api.notifications.notify_manager",
    },
}

scheduler_events = {
    "daily": [
        "designers.tasks.check_deadlines",
    ]
}

after_install = "designers.install.setup.after_install"
before_migrate = "designers.install.setup.before_migrate"
after_migrate = "designers.install.setup.after_migrate"

# Source of truth for roles/workflows/permissions is Python code in designers.install.security.
# Keep fixtures disabled for these entities to avoid drift/conflicts.
fixtures = []

override_whitelisted_methods = {
    "frappe.handler.upload_file": "designers.upload.restricted_upload_file"
}
