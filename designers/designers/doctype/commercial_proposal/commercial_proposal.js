// Copyright (c) 2026, Dmitriy and contributors
// For license information, please see license.txt

const TABLE_SECTIONS = [
	{
		title: "Содержание и стоимость работ на этапе проектирования",
		fieldname: "stages_json",
		columns: [
			{ key: "code", label: "Стадия" },
			{ key: "duration", label: "Срок", className: "center" },
			{ key: "workdays", label: "Трудоёмкость", className: "center" },
		],
	},
	{
		title: "Предпроектные работы",
		fieldname: "preproject_rows_json",
		columns: [
			{ key: "index", label: "№", className: "center" },
			{ key: "name", label: "Состав работ" },
			{ key: "code", label: "Обозн.", className: "center" },
			{ key: "price", label: "Стоимость ППД", className: "sum" },
		],
	},
	{
		title: "Базовое проектирование",
		fieldname: "project_rows_json",
		columns: [
			{ key: "index", label: "№", className: "center" },
			{ key: "name", label: "Состав работ" },
			{ key: "code", label: "Обозн.", className: "center" },
			{ key: "price", label: "Стоимость П", className: "sum" },
		],
	},
	{
		title: "Рабочее проектирование",
		fieldname: "working_rows_page1_json",
		columns: [
			{ key: "index", label: "№", className: "center" },
			{ key: "name", label: "Состав работ РД" },
			{ key: "code", label: "Обозн.", className: "center" },
			{ key: "price", label: "Стоимость РД", className: "sum" },
		],
	},
	{
		title: "Продолжение рабочей документации",
		fieldname: "working_rows_page2_json",
		columns: [
			{ key: "index", label: "№", className: "center" },
			{ key: "name", label: "Состав работ РД" },
			{ key: "code", label: "Обозн.", className: "center" },
		],
	},
];

const PREVIEW_FIELDS = [
	"city",
	"document_date",
	"offer_subject",
	"company_name",
	"stages_json",
	"preproject_rows_json",
	"project_rows_json",
	"working_rows_page1_json",
	"working_rows_page2_json",
];

const JSON_TABLE_EDITORS = [
	{
		title: "Стадии (сроки и трудоемкость)",
		fieldname: "stages_json",
		columns: [
			{ key: "code", label: "Стадия" },
			{ key: "duration", label: "Срок" },
			{ key: "workdays", label: "Трудоёмкость" },
		],
	},
	{
		title: "Предпроектные работы",
		fieldname: "preproject_rows_json",
		columns: [
			{ key: "index", label: "№" },
			{ key: "name", label: "Состав работ" },
			{ key: "code", label: "Обозн." },
			{ key: "price", label: "Стоимость ППД" },
		],
	},
	{
		title: "Базовое проектирование",
		fieldname: "project_rows_json",
		columns: [
			{ key: "index", label: "№" },
			{ key: "name", label: "Состав работ" },
			{ key: "code", label: "Обозн." },
			{ key: "price", label: "Стоимость П" },
		],
	},
	{
		title: "Рабочее проектирование",
		fieldname: "working_rows_page1_json",
		columns: [
			{ key: "index", label: "№" },
			{ key: "name", label: "Состав работ РД" },
			{ key: "code", label: "Обозн." },
			{ key: "price", label: "Стоимость РД" },
		],
	},
	{
		title: "Продолжение рабочей документации",
		fieldname: "working_rows_page2_json",
		columns: [
			{ key: "index", label: "№" },
			{ key: "name", label: "Состав работ РД" },
			{ key: "code", label: "Обозн." },
		],
	},
];

const JSON_TABLE_FIELDS = JSON_TABLE_EDITORS.map((editor) => editor.fieldname);

const PREVIEW_STYLE = `
	<style>
		.cp-live-preview {
			border: 1px solid #dce4f0;
			background: #fbfdff;
			padding: 12px;
			border-radius: 8px;
			margin-bottom: 16px;
		}

		.cp-live-preview__title {
			margin: 0 0 10px;
			font-size: 16px;
			font-weight: 600;
			color: #2a63ad;
		}

		.cp-live-preview__meta {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
			gap: 8px;
			margin-bottom: 12px;
			font-size: 13px;
		}

		.cp-live-preview__meta strong {
			color: #2a63ad;
		}

		.cp-live-preview__section {
			margin-top: 10px;
		}

		.cp-live-preview__section h5 {
			margin: 0 0 6px;
			font-size: 13px;
			color: #2a63ad;
			text-transform: uppercase;
			letter-spacing: 0.02em;
		}

		.cp-live-preview table {
			width: 100%;
			border-collapse: collapse;
			font-size: 12px;
			background: #fff;
		}

		.cp-live-preview th,
		.cp-live-preview td {
			border: 1px solid #d7dde7;
			padding: 6px 8px;
			text-align: left;
			vertical-align: top;
		}

		.cp-live-preview th {
			background: #e9f0fb;
			color: #2a63ad;
			text-transform: uppercase;
			font-size: 11px;
		}

		.cp-live-preview .center {
			text-align: center;
		}

		.cp-live-preview .sum {
			text-align: right;
			white-space: nowrap;
			font-weight: 600;
		}

		.cp-live-preview__note {
			margin-top: 6px;
			font-size: 12px;
			color: #7b7b7b;
		}
	</style>
`;

const JSON_EDITOR_STYLE = `
	<style>
		.cp-json-editor {
			border: 1px solid #dce4f0;
			background: #fbfdff;
			padding: 12px;
			border-radius: 8px;
			margin-bottom: 16px;
		}

		.cp-json-editor__section + .cp-json-editor__section {
			margin-top: 14px;
		}

		.cp-json-editor__title {
			margin: 0 0 8px;
			font-size: 14px;
			color: #2a63ad;
		}

		.cp-json-editor__table {
			width: 100%;
			border-collapse: collapse;
			background: #fff;
			font-size: 12px;
		}

		.cp-json-editor__table th,
		.cp-json-editor__table td {
			border: 1px solid #d7dde7;
			padding: 6px;
			vertical-align: middle;
		}

		.cp-json-editor__table th {
			background: #e9f0fb;
			color: #2a63ad;
			text-transform: uppercase;
			font-size: 11px;
		}

		.cp-json-editor__table input {
			width: 100%;
			border: 1px solid #d0d7e2;
			border-radius: 4px;
			padding: 5px 6px;
			font-size: 12px;
			background: #fff;
		}

		.cp-json-editor__actions {
			margin-top: 6px;
			display: flex;
			gap: 6px;
		}
	</style>
`;

function escapeHtml(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function parseJsonArray(value) {
	if (!value) {
		return [];
	}

	if (Array.isArray(value)) {
		return value;
	}

	try {
		const parsed = JSON.parse(value);
		return Array.isArray(parsed) ? parsed : [];
	} catch (error) {
		return null;
	}
}

function renderTableSection(section, rawValue) {
	const rows = parseJsonArray(rawValue);
	const title = `<h5>${escapeHtml(section.title)}</h5>`;

	if (rows === null) {
		return `
			<div class="cp-live-preview__section">
				${title}
				<div class="cp-live-preview__note">Невалидный JSON</div>
			</div>
		`;
	}

	if (!rows.length) {
		return `
			<div class="cp-live-preview__section">
				${title}
				<div class="cp-live-preview__note">Нет строк</div>
			</div>
		`;
	}

	const head = section.columns
		.map((column) => `<th>${escapeHtml(column.label)}</th>`)
		.join("");
	const body = rows
		.map((row) => {
			const cells = section.columns
				.map((column) => {
					const classAttr = column.className ? ` class="${column.className}"` : "";
					return `<td${classAttr}>${escapeHtml(row?.[column.key])}</td>`;
				})
				.join("");
			return `<tr>${cells}</tr>`;
		})
		.join("");

	return `
		<div class="cp-live-preview__section">
			${title}
			<table>
				<thead><tr>${head}</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</div>
	`;
}

function renderLivePreview(frm) {
	const previewField = frm.get_field("live_print_preview_html");
	if (!previewField) {
		return;
	}

	const metaHtml = `
		<div class="cp-live-preview__meta">
			<div><strong>Город:</strong> ${escapeHtml(frm.doc.city)}</div>
			<div><strong>Дата:</strong> ${escapeHtml(frm.doc.document_date)}</div>
			<div><strong>Тема:</strong> ${escapeHtml(frm.doc.offer_subject)}</div>
			<div><strong>Компания:</strong> ${escapeHtml(frm.doc.company_name)}</div>
		</div>
	`;

	const tableHtml = TABLE_SECTIONS.map((section) =>
		renderTableSection(section, frm.doc[section.fieldname])
	).join("");

	previewField.$wrapper.html(`
		${PREVIEW_STYLE}
		<div class="cp-live-preview">
			<h4 class="cp-live-preview__title">Live Preview (как в Print Format)</h4>
			${metaHtml}
			${tableHtml}
		</div>
	`);
}

function normalizeRows(rows, columns) {
	return rows.map((row) => {
		const normalized = {};
		columns.forEach((column) => {
			normalized[column.key] = row?.[column.key] == null ? "" : String(row[column.key]);
		});
		return normalized;
	});
}

function getEditorRows(frm, editor) {
	const parsed = parseJsonArray(frm.doc[editor.fieldname]);
	if (parsed === null) {
		return [];
	}
	return normalizeRows(parsed, editor.columns);
}

function commitEditorRows(frm, editor, rows) {
	const normalized = normalizeRows(rows, editor.columns);
	frm.__cp_json_editor_cache = frm.__cp_json_editor_cache || {};
	frm.__cp_json_editor_cache[editor.fieldname] = normalized;
	frm.set_value(editor.fieldname, JSON.stringify(normalized, null, 2));
}

function renderJsonTableEditors(frm) {
	const editorField = frm.get_field("json_tables_editor_html");
	if (!editorField) {
		return;
	}

	frm.__cp_json_editor_cache = frm.__cp_json_editor_cache || {};
	const sections = JSON_TABLE_EDITORS.map((editor) => {
		const rows = frm.__cp_json_editor_cache[editor.fieldname] || getEditorRows(frm, editor);
		frm.__cp_json_editor_cache[editor.fieldname] = rows;

		const head = editor.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("");
		const body = rows
			.map((row, rowIndex) => {
				const cells = editor.columns
					.map((column) => {
						const value = escapeHtml(row[column.key]);
						return `<td><input data-json-editor-input="1" data-field="${editor.fieldname}" data-row="${rowIndex}" data-key="${column.key}" value="${value}" /></td>`;
					})
					.join("");
				return `<tr>${cells}<td><button class="btn btn-xs btn-secondary" data-remove-row="1" data-field="${editor.fieldname}" data-row="${rowIndex}" type="button">Удалить</button></td></tr>`;
			})
			.join("");

		return `
			<div class="cp-json-editor__section">
				<h5 class="cp-json-editor__title">${escapeHtml(editor.title)}</h5>
				<table class="cp-json-editor__table">
					<thead>
						<tr>${head}<th>Действия</th></tr>
					</thead>
					<tbody>${body || `<tr><td colspan="${editor.columns.length + 1}">Нет строк</td></tr>`}</tbody>
				</table>
				<div class="cp-json-editor__actions">
					<button class="btn btn-xs btn-primary" data-add-row="1" data-field="${editor.fieldname}" type="button">Добавить строку</button>
				</div>
			</div>
		`;
	}).join("");

	editorField.$wrapper.html(`
		${JSON_EDITOR_STYLE}
		<div class="cp-json-editor">
			${sections}
		</div>
	`);

	JSON_TABLE_FIELDS.forEach((fieldname) => {
		if (frm.fields_dict[fieldname]) {
			frm.toggle_display(fieldname, false);
		}
	});

	if (!frm.__cp_json_editor_events_bound) {
		frm.__cp_json_editor_events_bound = true;

		editorField.$wrapper.on("input", "[data-json-editor-input]", (event) => {
			const target = event.currentTarget;
			const fieldname = target.dataset.field;
			const rowIndex = Number(target.dataset.row);
			const key = target.dataset.key;
			const editor = JSON_TABLE_EDITORS.find((item) => item.fieldname === fieldname);
			if (!editor) {
				return;
			}

			const rows = frm.__cp_json_editor_cache[fieldname] || getEditorRows(frm, editor);
			if (!rows[rowIndex]) {
				return;
			}

			rows[rowIndex][key] = target.value || "";
			commitEditorRows(frm, editor, rows);
		});

		editorField.$wrapper.on("click", "[data-add-row]", (event) => {
			const fieldname = event.currentTarget.dataset.field;
			const editor = JSON_TABLE_EDITORS.find((item) => item.fieldname === fieldname);
			if (!editor) {
				return;
			}

			const rows = frm.__cp_json_editor_cache[fieldname] || getEditorRows(frm, editor);
			const newRow = {};
			editor.columns.forEach((column) => {
				newRow[column.key] = "";
			});
			rows.push(newRow);
			commitEditorRows(frm, editor, rows);
			renderJsonTableEditors(frm);
			renderLivePreview(frm);
		});

		editorField.$wrapper.on("click", "[data-remove-row]", (event) => {
			const fieldname = event.currentTarget.dataset.field;
			const rowIndex = Number(event.currentTarget.dataset.row);
			const editor = JSON_TABLE_EDITORS.find((item) => item.fieldname === fieldname);
			if (!editor) {
				return;
			}

			const rows = frm.__cp_json_editor_cache[fieldname] || getEditorRows(frm, editor);
			rows.splice(rowIndex, 1);
			commitEditorRows(frm, editor, rows);
			renderJsonTableEditors(frm);
			renderLivePreview(frm);
		});
	}
}

frappe.ui.form.on("Commercial Proposal", {
	refresh(frm) {
		const hideWorkflowActions = () => {
			frm.page.wrapper
				.find(".workflow-action, .btn-workflow, .workflow-button-area")
				.closest("button, a, li, .btn-group")
				.remove();
		};

		// Workflow transitions are executed from Tender Request only.
		hideWorkflowActions();
		setTimeout(hideWorkflowActions, 100);

		if (!frm.__cp_live_preview_handler) {
			frm.__cp_live_preview_handler = frappe.utils.debounce(() => renderLivePreview(frm), 200);
			frm.$wrapper.on(
				"input.cp-live-preview change.cp-live-preview",
				"input, textarea, .ace_text-input",
				frm.__cp_live_preview_handler
			);
		}

		renderJsonTableEditors(frm);
		renderLivePreview(frm);
	},
});

PREVIEW_FIELDS.forEach((fieldname) => {
	frappe.ui.form.on("Commercial Proposal", {
		[fieldname](frm) {
			if (JSON_TABLE_FIELDS.includes(fieldname)) {
				renderJsonTableEditors(frm);
			}
			renderLivePreview(frm);
		},
	});
});
