// Copyright (c) 2026, Dmitriy and contributors
// For license information, please see license.txt

function isDocxUrl(fileUrl) {
	const normalized = (fileUrl || "").split("?", 1)[0].toLowerCase();
	return normalized.endsWith(".docx");
}

async function openClientAttachmentsDialog(frm) {
	if (frm.is_new() || !frm.doc.name) {
		frappe.msgprint(__("Please save the document first."));
		return;
	}

	const response = await frappe.call({
		method: "designers.designers.doctype.commercial_proposal.commercial_proposal.get_client_send_attachments",
		args: { proposal_name: frm.doc.name },
	});

	const files = response.message?.files || [];
	if (!files.length) {
		frappe.msgprint(__("No attachments found. Attach files first."));
		return;
	}

	const rows = files
		.map(
			(file, index) => `
				<label style="display:flex; align-items:center; gap:8px; margin: 0 0 8px 0;">
					<input type="checkbox" data-file="${frappe.utils.escape_html(file.name)}" ${file.selected ? "checked" : ""}/>
					<span>${index + 1}. ${frappe.utils.escape_html(file.file_name || file.file_url || file.name)}</span>
				</label>
			`
		)
		.join("");

	const dialog = new frappe.ui.Dialog({
		title: __("Select Attachments For Client"),
		size: "large",
		fields: [
			{
				fieldname: "attachments_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Save"),
		primary_action: async () => {
			const selected = [];
			dialog.$wrapper.find("input[type='checkbox'][data-file]").each((_, node) => {
				if (node.checked) {
					selected.push(node.getAttribute("data-file"));
				}
			});

			await frappe.call({
				method: "designers.designers.doctype.commercial_proposal.commercial_proposal.set_client_send_attachments",
				args: {
					proposal_name: frm.doc.name,
					selected_file_docnames: selected,
				},
			});

			frappe.show_alert({
				message: __("{0} file(s) selected for client email", [selected.length]),
				indicator: "green",
			});
			dialog.hide();
			await frm.reload_doc();
		},
	});

	dialog.fields_dict.attachments_html.$wrapper.html(`
		<div style="max-height: 60vh; overflow:auto; padding-right: 8px;">
			${rows}
		</div>
	`);
	dialog.show();
}

async function openClientEmailComposer(frm) {
	if (frm.is_new() || !frm.doc.name) {
		frappe.msgprint(__("Please save the document first."));
		return;
	}
	if (Number(frm.doc.sent_to_client || 0) === 1) {
		frappe.msgprint({
			title: __("Письмо уже отправлено"),
			indicator: "orange",
			message: __("Для этого Commercial Proposal письмо клиенту уже было отправлено."),
		});
		return;
	}

	const response = await frappe.call({
		method: "designers.designers.doctype.commercial_proposal.commercial_proposal.get_client_email_context",
		args: { proposal_name: frm.doc.name },
	});
	const context = response.message || {};
	const recipients = context.recipients || [];

	if (!recipients.length) {
		frappe.msgprint(__("Primary customer email is required."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Письмо клиенту"),
		size: "large",
		fields: [
			{
				fieldname: "recipients",
				fieldtype: "Data",
				label: __("Кому"),
				reqd: 1,
				default: recipients.join(", "),
			},
			{
				fieldname: "subject",
				fieldtype: "Data",
				label: __("Тема"),
				reqd: 1,
				default: context.subject || `Commercial Proposal: ${frm.doc.name}`,
			},
			{
				fieldname: "message",
				fieldtype: "Text Editor",
				label: __("Сообщение"),
				default: context.message || "",
			},
		],
		primary_action_label: __("Отправить"),
		primary_action: async (values) => {
			await frappe.call({
				method:
					"designers.designers.doctype.commercial_proposal.commercial_proposal.send_client_email_from_ui",
				args: {
					proposal_name: frm.doc.name,
					recipients: values.recipients,
					subject: values.subject,
					message: values.message || "",
				},
			});
			frappe.show_alert({ message: __("Письмо отправлено"), indicator: "green" });
			dialog.hide();
			await frm.reload_doc();
		},
	});
	dialog.show();
}

async function uploadOrReplaceProposalDocx(frm) {
	if (frm.is_new() || !frm.doc.name) {
		frappe.msgprint(__("Please save the document first."));
		return false;
	}

	return new Promise((resolve) => {
		frappe.prompt(
			[
				{
					fieldname: "docx_file",
					fieldtype: "Attach",
					label: __("Proposal DOCX"),
					reqd: 1,
				},
			],
			async (values) => {
				if (!isDocxUrl(values.docx_file)) {
					frappe.msgprint(__("Please upload a .docx file."));
					resolve(false);
					return;
				}

				await frappe.call({
					method: "designers.designers.doctype.commercial_proposal.commercial_proposal.attach_proposal_docx",
					args: {
						proposal_name: frm.doc.name,
						file_url: values.docx_file,
					},
				});

				await frm.reload_doc();
				frappe.show_alert({ message: __("Proposal.docx attached"), indicator: "green" });
				resolve(true);
			},
			__("Upload/Replace DOCX"),
			__("Save")
		);
	});
}

function loadOnlyOfficeScript(documentServerUrl) {
	const scriptUrl = `${documentServerUrl}/web-apps/apps/api/documents/api.js`;
	if (window.DocsAPI) {
		return Promise.resolve();
	}
	if (window.__onlyofficeScriptPromise) {
		return window.__onlyofficeScriptPromise;
	}

	window.__onlyofficeScriptPromise = new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = scriptUrl;
		script.onload = () => resolve();
		script.onerror = () => reject(new Error(`Failed to load OnlyOffice script: ${scriptUrl}`));
		document.head.appendChild(script);
	});

	return window.__onlyofficeScriptPromise;
}

async function openOnlyOfficeEditor(frm) {
	if (frm.is_new() || !frm.doc.name) {
		frappe.msgprint(__("Please save the document first."));
		return;
	}

	if (!isDocxUrl(frm.doc.proposal_file)) {
		const uploaded = await uploadOrReplaceProposalDocx(frm);
		if (!uploaded || !isDocxUrl(frm.doc.proposal_file)) {
			return;
		}
	}

	const response = await frappe.call({
		method: "designers.designers.doctype.commercial_proposal.commercial_proposal.get_onlyoffice_editor_config",
		args: { proposal_name: frm.doc.name },
	});
	const payload = response.message || {};
	if (!payload.document_server_url || !payload.config) {
		frappe.msgprint(__("OnlyOffice is not configured."));
		return;
	}

	await loadOnlyOfficeScript(payload.document_server_url);
	if (!window.DocsAPI) {
		frappe.throw(__("OnlyOffice API is not available."));
	}

	payload.config.events = {
		...(payload.config.events || {}),
		onError(event) {
			console.error("OnlyOffice error", event);
			const code = event?.data?.errorCode || event?.data?.code || "";
			const description = event?.data?.errorDescription || event?.data?.message || "";
			frappe.msgprint(
				__("OnlyOffice error") + (code ? ` (${code})` : "") + (description ? `: ${description}` : "")
			);
		},
	};

	const editorContainerId = `onlyoffice-editor-${frappe.utils.get_random(8)}`;
	const dialog = new frappe.ui.Dialog({
		title: __("Edit DOCX"),
		size: "extra-large",
		fields: [{ fieldname: "onlyoffice_info", fieldtype: "HTML" }],
		primary_action_label: __("Close"),
		primary_action: async () => {
			dialog.hide();
			await frm.reload_doc();
		},
	});
	dialog.$wrapper.addClass("cp-onlyoffice-dialog");

	dialog.fields_dict.onlyoffice_info.$wrapper.html(`
		<div class="cp-onlyoffice-root" style="height:100%; min-height:100%; display:flex; flex-direction:column;">
			<div class="cp-onlyoffice-hint" style="margin-bottom: 8px; color: #6b7280; font-size: 12px; flex:0 0 auto;">
				${__("Save in OnlyOffice, then close this dialog to refresh DOCX file")}
			</div>
			<div class="cp-onlyoffice-editor-slot" style="position:relative; flex:1 1 auto; min-height:0; width:100%;">
				<div id="${editorContainerId}" style="position:absolute; inset:0; width:100%; height:100%; border: 1px solid #e5e7eb;"></div>
			</div>
		</div>
	`);

	dialog.$wrapper.find(".modal-dialog").css({
		width: "98vw",
		maxWidth: "98vw",
		height: "98vh",
		margin: "1vh auto",
	});
	dialog.$wrapper.find(".modal-content").css({
		height: "98vh",
		display: "flex",
		flexDirection: "column",
	});
	dialog.$wrapper.find(".modal-body").css({
		height: "calc(98vh - 95px)",
		overflow: "hidden",
		display: "flex",
		flexDirection: "column",
		paddingBottom: "0",
	});
	dialog.fields_dict.onlyoffice_info.$wrapper.css({
		height: "100%",
		display: "flex",
		flexDirection: "column",
	});

	const forceModalFieldFullHeight = () => {
		dialog.$wrapper
			.find(
				".form-layout, .form-page, .page-body, .form-section, .section-body, .form-column, .frappe-control[data-fieldname='onlyoffice_info'], .control-input-wrapper, .control-value, form, .cp-onlyoffice-root"
			)
			.each((_, node) => {
				node.style.setProperty("height", "100%", "important");
				node.style.setProperty("min-height", "100%", "important");
				node.style.setProperty("max-height", "none", "important");
				node.style.setProperty("display", "flex", "important");
				node.style.setProperty("flex-direction", "column", "important");
				node.style.setProperty("flex", "1 1 auto", "important");
				node.style.setProperty("min-width", "0", "important");
			});
	};

	const applyFullHeight = () => {
		const editorEl = dialog.$wrapper.find(`#${editorContainerId}`).get(0);
		const modalBodyEl = dialog.$wrapper.find(".modal-body").get(0);
		const hintEl = dialog.$wrapper.find(".cp-onlyoffice-hint").get(0);
		const slotEl = dialog.$wrapper.find(".cp-onlyoffice-editor-slot").get(0);
		forceModalFieldFullHeight();
		if (editorEl && slotEl) {
			const bodyHeight = modalBodyEl?.clientHeight || Math.floor((window.innerHeight || 900) - 130);
			const hintHeight = hintEl?.offsetHeight || 0;
			const targetHeight = Math.max(640, bodyHeight - hintHeight - 8);
			slotEl.style.setProperty("height", `${targetHeight}px`, "important");
			slotEl.style.setProperty("min-height", `${targetHeight}px`, "important");
			slotEl.style.setProperty("max-height", "none", "important");
			slotEl.style.setProperty("flex", "1 1 auto", "important");
			editorEl.style.setProperty("height", `${targetHeight}px`, "important");
			editorEl.style.setProperty("min-height", `${targetHeight}px`, "important");
			editorEl.style.setProperty("max-height", "none", "important");
			editorEl.style.setProperty("flex", "1 1 auto", "important");
			editorEl.style.setProperty("position", "absolute", "important");
			editorEl.style.setProperty("inset", "0px", "important");
		}
	};

	let docEditor = null;
	const initEditor = () => {
		try {
			applyFullHeight();
			docEditor = new window.DocsAPI.DocEditor(editorContainerId, payload.config);
		} catch (error) {
			dialog.hide();
			frappe.throw(error.message || __("Failed to initialize OnlyOffice editor."));
		}
	};

	dialog.$wrapper.one("shown.bs.modal", () => {
		applyFullHeight();
		setTimeout(initEditor, 50);
	});
	dialog.show();
	$(window).on("resize.cp_onlyoffice_dialog", applyFullHeight);

	dialog.$wrapper.on("hide.bs.modal", () => {
		$(window).off("resize.cp_onlyoffice_dialog");
		try {
			docEditor?.destroyEditor?.();
		} catch (error) {
			// no-op
		}
	});
}

frappe.ui.form.on("Commercial Proposal", {
	refresh(frm) {
		const composeEmailLabel = __("Письмо");
		const uploadLabel = __("Загрузить КП");
		const editLabel = __("Изменить КП");
		const selectAttachmentsLabel = __("Вложить приложения");
		const userRoles = Array.isArray(frappe.user_roles) ? frappe.user_roles : [];
		const isBizManager = userRoles.includes("Biz Manager") || frappe.session.user === "Administrator";
		const status = frm.doc.status || "";
		const canComposeEmail = ["Admin Approved", "Sent"].includes(status) && isBizManager;

		if (canComposeEmail) {
			frm.add_custom_button(composeEmailLabel, () => openClientEmailComposer(frm));
		}
		frm.add_custom_button(uploadLabel, () => uploadOrReplaceProposalDocx(frm));
		frm.add_custom_button(editLabel, () => openOnlyOfficeEditor(frm));
		frm.add_custom_button(selectAttachmentsLabel, () => openClientAttachmentsDialog(frm));
		if (!frm.__cp_actions_menu_bound) {
			frm.__cp_actions_menu_bound = true;
			if (canComposeEmail) {
				frm.page.add_action_item(composeEmailLabel, () => openClientEmailComposer(frm));
			}
			frm.page.add_action_item(uploadLabel, () => uploadOrReplaceProposalDocx(frm));
			frm.page.add_action_item(editLabel, () => openOnlyOfficeEditor(frm));
			frm.page.add_action_item(selectAttachmentsLabel, () => openClientAttachmentsDialog(frm));
		}

		if (frm.doc.proposal_file && isDocxUrl(frm.doc.proposal_file)) {
			const openDocx = () => {
				window.open(frm.doc.proposal_file, "_blank");
			};
			frm.page.add_action_item(__("Скачать КП"), openDocx);
		}
	},
});
