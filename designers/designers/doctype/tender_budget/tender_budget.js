// Copyright (c) 2026, Dmitriy and contributors
// For license information, please see license.txt

function escapeHtml(value) {
	const s = value == null ? "" : String(value);
	return s
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#039;");
}

function renderCompareHtml(result) {
	const summary = result.summary || {};
	const changes = result.changes || [];
	const added = (summary.added_sheets || []).join(", ") || "None";
	const removed = (summary.removed_sheets || []).join(", ") || "None";

	const rows = changes.length
		? changes
				.map(
					(row) => `
						<tr>
							<td>${escapeHtml(row.sheet)}</td>
							<td>${escapeHtml(row.cell)}</td>
							<td>${escapeHtml(row.old)}</td>
							<td>${escapeHtml(row.new)}</td>
						</tr>
					`
				)
				.join("")
		: `<tr><td colspan="4">${__("No changed cells found")}</td></tr>`;

	const truncatedNote = summary.truncated
		? `<p style="margin-top:8px;color:#b54708;">${__(
				"Result is truncated to first {0} changes",
				[summary.max_changes || 500]
		  )}</p>`
		: "";

	return `
		<div>
			<p><b>${__("From")}:</b> ${escapeHtml(result.from?.name)} (v${escapeHtml(result.from?.version)})</p>
			<p><b>${__("To")}:</b> ${escapeHtml(result.to?.name)} (v${escapeHtml(result.to?.version)})</p>
			<p><b>${__("Added sheets")}:</b> ${escapeHtml(added)}</p>
			<p><b>${__("Removed sheets")}:</b> ${escapeHtml(removed)}</p>
			<p><b>${__("Changed cells")}:</b> ${escapeHtml(summary.changes_count || 0)}</p>
			<div style="max-height:360px;overflow:auto;border:1px solid #e5e7eb;border-radius:8px;">
				<table class="table table-bordered" style="margin-bottom:0;">
					<thead>
						<tr>
							<th>${__("Sheet")}</th>
							<th>${__("Cell")}</th>
							<th>${__("Old value")}</th>
							<th>${__("New value")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			${truncatedNote}
		</div>
	`;
}

async function showCompareDialog(frm) {
	const currentVersion = cint(frm.doc.version || 0);
	const defaultFrom = currentVersion > 1 ? currentVersion - 1 : currentVersion;
	const defaultTo = currentVersion;

	frappe.prompt(
		[
			{
				fieldname: "from_version",
				fieldtype: "Int",
				label: __("From version"),
				reqd: 1,
				default: defaultFrom,
			},
			{
				fieldname: "to_version",
				fieldtype: "Int",
				label: __("To version"),
				reqd: 1,
				default: defaultTo,
			},
		],
		async (values) => {
			const response = await frappe.call({
				method: "designers.designers.doctype.tender_budget.tender_budget.compare_budget_versions",
				args: {
					tender_request: frm.doc.tender_request,
					from_version: values.from_version,
					to_version: values.to_version,
				},
			});

			const result = response.message || {};
			frappe.msgprint({
				title: __("Version comparison"),
				message: renderCompareHtml(result),
				wide: true,
			});
		},
		__("Compare Tender Budget versions"),
		__("Compare")
	);
}

frappe.ui.form.on("Tender Budget", {
	refresh(frm) {
		const hideWorkflowActions = () => {
			frm.page.wrapper
				.find(".workflow-action, .btn-workflow, .workflow-button-area")
				.closest("button, a, li, .btn-group")
				.remove();
		};

		// Workflow transitions are executed from Tender Request only.
		// Keep child form read-only from workflow perspective.
		hideWorkflowActions();
		setTimeout(hideWorkflowActions, 100);

		if (frm.doc.budget_file) {
			frm.add_custom_button(__("Open Budget File"), () => {
				window.open(frm.doc.budget_file, "_blank");
			});
		}

		if (!frm.is_new() && frm.doc.tender_request) {
			frm.add_custom_button(__("Compare Versions"), () => showCompareDialog(frm));
		}
	},
});
