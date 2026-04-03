frappe.ui.form.on("Tender Request", {
  onload(frm) {
    if (frm.__designers_auto_refresh_timer) return;

    const pollForUpdates = async () => {
      if (frm.is_new() || frm.is_dirty()) return;
      if (!frm.doc?.name) return;

      try {
        const res = await frappe.db.get_value("Tender Request", frm.doc.name, ["modified"]);
        const serverModified = res?.message?.modified;
        if (serverModified && frm.doc.modified && serverModified !== frm.doc.modified) {
          await frm.reload_doc();
        }
      } catch (e) {
        // Keep UI responsive even if a transient network/API issue occurs.
      }
    };

    frm.__designers_auto_refresh_timer = setInterval(() => {
      pollForUpdates();
    }, 4000);
  },

  onhide(frm) {
    if (frm.__designers_auto_refresh_timer) {
      clearInterval(frm.__designers_auto_refresh_timer);
      frm.__designers_auto_refresh_timer = null;
    }
  },

  async refresh(frm) {
    if (frm.is_new()) return;
    const visibilityResponse = await frappe.call({
      method: "designers.designers.doctype.tender_request.tender_request.get_action_visibility",
      args: { tender_request: frm.doc.name },
    });
    const v = visibilityResponse.message || {};

    if (v.edit_access) {
      frm.add_custom_button(__("Edit Access"), async () => {
        const currentUsers = (frm.doc.access_users || [])
          .map((row) => row.user)
          .filter(Boolean);

        frappe.prompt(
          [
            {
              fieldname: "users",
              fieldtype: "MultiSelectPills",
              label: __("Allowed Users"),
              default: currentUsers,
              get_data: (txt) =>
                frappe.db.get_link_options("User", txt, {
                  enabled: 1,
                }),
            },
          ],
          async (values) => {
            await frappe.call({
              method: "designers.designers.doctype.tender_request.tender_request.update_access_users",
              args: {
                tender_request: frm.doc.name,
                users: values.users || [],
              },
            });
            frappe.show_alert({ message: __("Access updated"), indicator: "green" });
            await frm.reload_doc();
          },
          __("Edit Access"),
          __("Save")
        );
      });
    }

    const callAction = async (method, successMessage) => {
      await frappe.call({
        method,
        args: { tender_request: frm.doc.name },
      });
      frappe.show_alert({ message: __(successMessage), indicator: "green" });
      await frm.reload_doc();
    };

    if (v.send_budget_to_director) {
      frm.add_custom_button(__("Send Budget To Director"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.send_budget_to_director",
          "Budget sent to director",
        ),
      );
    }

    if (v.approve_director) {
      frm.add_custom_button(__("Approve Director"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.approve_budget_director",
          "Director approved budget",
        ),
      );
    }

    if (v.approve_budget) {
      frm.add_custom_button(__("Approve Budget"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.approve_budget_ceo",
          "Budget approved",
        ),
      );
    }

    if (v.submit_proposal) {
      frm.add_custom_button(__("Submit Proposal"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.submit_proposal_for_approval",
          "Proposal sent for approval",
        ),
      );
    }

    if (v.approve_proposal) {
      frm.add_custom_button(__("Approve Proposal"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.approve_proposal",
          "Proposal approved",
        ),
      );
    }

    if (v.send_to_admin) {
      frm.add_custom_button(__("Send To Admin"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.send_proposal_to_admin",
          "Proposal sent to admin",
        ),
      );
    }

    if (v.approve_by_admin) {
      frm.add_custom_button(__("Approve By Admin"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.approve_proposal_by_admin",
          "Proposal approved by admin",
        ),
      );
    }

    if (v.send_to_client) {
      frm.add_custom_button(__("Send To Client"), () =>
        callAction(
          "designers.designers.doctype.tender_request.tender_request.send_to_client",
          "Sent to client",
        ),
      );
    }
  },
});
