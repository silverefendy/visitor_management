frappe.pages["vms-data-cleanup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("VMS Data Cleanup"),
		single_column: true,
	});

	const state = { records: [] };
	const $body = $(page.body).addClass("vms-cleanup-page");
	$body.html(`
		<div class="vms-cleanup-shell">
			<div class="vms-cleanup-card">
				<h3>${__("Filter Old Visitor Records")}</h3>
				<div class="vms-cleanup-grid" id="cleanup-filters"></div>
				<div class="vms-cleanup-actions">
					<button class="btn btn-primary" id="cleanup-preview">${__("Preview Records")}</button>
					<button class="btn btn-default" id="cleanup-select-all">${__("Select All")}</button>
					<button class="btn btn-warning" id="cleanup-archive">${__("Archive Selected")}</button>
					<button class="btn btn-danger" id="cleanup-delete">${__("Delete Selected")}</button>
				</div>
			</div>
			<div class="vms-cleanup-card">
				<div class="vms-cleanup-summary" id="cleanup-summary">${__("No preview loaded.")}</div>
				<div class="table-responsive"><table class="table table-bordered" id="cleanup-table"></table></div>
			</div>
		</div>
	`);

	const fields = [
		{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
		{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
		{ fieldname: "older_than_days", fieldtype: "Int", label: __("Older Than X Days") },
		{ fieldname: "status", fieldtype: "Select", label: __("Visitor Status"), options: "\nRegistered\nAwaiting Approval\nApproved\nChecked In\nCompleted\nChecked Out\nRejected\nCancelled\nArchived" },
		{ fieldname: "checked_out_only", fieldtype: "Check", label: __("Checked Out Only") },
		{ fieldname: "gate", fieldtype: "Link", label: __("Gate"), options: "Gate" },
		{ fieldname: "company", fieldtype: "Data", label: __("Company") },
		{ fieldname: "visitor_type", fieldtype: "Select", label: __("Visitor Type"), options: "\nKTP\nSIM\nPaspor\nKartu Pelajar\nLainnya" },
	];
	const controls = {};
	fields.forEach((df) => {
		const control = frappe.ui.form.make_control({ parent: $body.find("#cleanup-filters"), df, render_input: true });
		control.refresh();
		controls[df.fieldname] = control;
	});

	function get_filters() {
		return Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.get_value()]).filter(([, value]) => value));
	}

	function selected_records() {
		return $body.find(".cleanup-check:checked").map((_, el) => $(el).data("name")).get();
	}

	function render_table(records) {
		state.records = records || [];
		$body.find("#cleanup-summary").text(__("{0} records ready for review.", [state.records.length]));
		$body.find("#cleanup-table").html(`
			<thead><tr><th></th><th>${__("Visitor")}</th><th>${__("Name")}</th><th>${__("Company")}</th><th>${__("Status")}</th><th>${__("Check In")}</th><th>${__("Check Out")}</th><th>${__("Modified")}</th></tr></thead>
			<tbody>${state.records.map((row) => `
				<tr>
					<td><input type="checkbox" class="cleanup-check" data-name="${frappe.utils.escape_html(row.name)}"></td>
					<td>${frappe.utils.escape_html(row.name || "")}</td>
					<td>${frappe.utils.escape_html(row.visitor_name || "")}</td>
					<td>${frappe.utils.escape_html(row.visitor_company || "")}</td>
					<td>${frappe.utils.escape_html(row.status || "")}</td>
					<td>${frappe.utils.escape_html(row.check_in_time || "")}</td>
					<td>${frappe.utils.escape_html(row.check_out_time || "")}</td>
					<td>${frappe.utils.escape_html(row.modified || "")}</td>
				</tr>`).join("")}</tbody>
		`);
	}

	function preview() {
		frappe.call({
			method: "visitor_management.visitor_management.maintenance.preview_cleanup_records",
			args: { filters: get_filters(), limit: 200 },
			freeze: true,
			callback: (r) => render_table((r.message && r.message.records) || []),
		});
	}

	function run(action) {
		const names = selected_records();
		if (!names.length) {
			frappe.msgprint(__("Select at least one record from the preview table."));
			return;
		}
		const is_delete = action === "Delete";
		const execute = (values = {}) => {
			frappe.confirm(__("Run {0} for {1} selected records?", [action, names.length]), () => {
				frappe.call({
					method: "visitor_management.visitor_management.maintenance.run_cleanup",
					args: { action, records: names, filters: get_filters(), confirm_text: values.confirm_text, archive_before_delete: 1 },
					freeze: true,
					callback: (r) => {
						frappe.msgprint((r.message && r.message.message) || __("Cleanup completed."));
						preview();
					},
				});
			});
		};
		if (is_delete) {
			frappe.prompt([{ fieldname: "confirm_text", fieldtype: "Data", label: __("Type DELETE to confirm"), reqd: 1 }], execute, __("Confirm Cleanup"), action);
		} else {
			execute();
		}
	}

	$body.find("#cleanup-preview").on("click", preview);
	$body.find("#cleanup-select-all").on("click", () => $body.find(".cleanup-check").prop("checked", true));
	$body.find("#cleanup-archive").on("click", () => run("Archive"));
	$body.find("#cleanup-delete").on("click", () => run("Delete"));
};
