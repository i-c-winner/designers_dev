import frappe


CLIENT_SCRIPT = """
frappe.web_form.validate = () => {
    const phone = (frappe.web_form.get_value("your_phone") || "").trim();
    const regex = /^\\+?[0-9]{10,15}$/;

    if (phone && !regex.test(phone)) {
        frappe.msgprint("Поле 'Ваш телефон' должно быть в формате +79991234567 (10-15 цифр).");
        return false;
    }

    return true;
};
"""


def execute():
    web_forms = frappe.get_all(
        "Web Form",
        filters={"route": "request-from-guest"},
        pluck="name",
    )

    for web_form_name in web_forms:
        web_form = frappe.get_doc("Web Form", web_form_name)
        if web_form.client_script != CLIENT_SCRIPT.strip():
            web_form.client_script = CLIENT_SCRIPT.strip()
            web_form.save(ignore_permissions=True)

    if web_forms:
        frappe.db.commit()
