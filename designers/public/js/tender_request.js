const CONTACT_PHONE_REGEX = /^\+7-(?:\d{3}|\(\d{3}\))-\d{3}-\d{2}-\d{2}$/;
const CONTACT_PHONE_HINT = "Формат телефона: +7-999-123-45-67 или +7-(999)-123-45-67";

function validateContactPhone(frm) {
    const value = (frm.doc.contact_phone || "").trim();
    if (!value) return;
    if (!CONTACT_PHONE_REGEX.test(value)) {
        frappe.throw(CONTACT_PHONE_HINT);
    }
}

frappe.ui.form.on("Tender Request", {
    validate(frm) {
        validateContactPhone(frm);
    },

    contact_phone(frm) {
        validateContactPhone(frm);
    },

    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button("Create Budget", () => {
            frappe.new_doc("Tender Budget", {
                tender_request: frm.doc.name,
            });
        });

        frm.add_custom_button("Create Proposal", async () => {
            const approvedBudgets = await frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Tender Budget",
                    filters: {
                        tender_request: frm.doc.name,
                        status: "Approved",
                    },
                    fields: ["name", "version"],
                    order_by: "version desc",
                    limit_page_length: 1,
                },
            });

            const approvedBudget = approvedBudgets.message?.[0];
            if (!approvedBudget) {
                frappe.msgprint(__("Сначала согласуйте Tender Budget (status = Approved)."));
                return;
            }

            await frappe.call({
                method: "designers.api.tender.create_proposal",
                args: {
                    tender_request: frm.doc.name,
                    tender_budget: approvedBudget.name,
                },
            });
            frappe.show_alert({ message: "Commercial Proposal created", indicator: "green" });
            frm.reload_doc();
        });

        frm.add_custom_button("Send To Client", async () => {
            await frappe.call({
                method: "designers.designers.doctype.tender_request.tender_request.send_to_client",
                args: {
                    tender_request: frm.doc.name,
                },
            });
            frappe.show_alert({ message: "Sent to client", indicator: "green" });
            frm.reload_doc();
        });
    },
});
