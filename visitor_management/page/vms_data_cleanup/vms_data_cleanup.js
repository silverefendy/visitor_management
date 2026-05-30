frappe.pages["vms-data-cleanup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("VMS Cleanup Tool"),
		single_column: true,
	});

	const state = { records: [], count: 0, target_doctype: "Visitor" };
	const $body = $(page.body).addClass("vms-cleanup-page");
	$body.html(`
		<div class="vms-cleanup-shell">
			<div class="vms-cleanup-card">
				<h3>${__("VMS Cleanup Tool")}</h3>
				<p class="text-muted">${__("Filter by DocType and date, preview counts, run safe dry-runs, delete selected records, or queue all filtered records in the background. Cleanup history is generated automatically and cannot be manually created.")}</p>
				<div class="vms-cleanup-grid" id="cleanup-filters"></div>
				<div class="vms-cleanup-actions">
					<button class="btn btn-primary" id="cleanup-preview">${__("Preview Records")}</button>
					<button class="btn btn-default" id="cleanup-select-all">${__("Select All")}</button>
					<button class="btn btn-default" id="cleanup-dry-run">${__("Dry Run Filtered")}</button>
					<button class="btn btn-danger" id="cleanup-delete-selected">${__("Delete Selected")}</button>
					<button class="btn btn-danger" id="cleanup-delete-filtered">${__("Delete All Filtered")}</button>
					<button class="btn btn-warning" id="cleanup-background">${__("Queue Filtered Delete")}</button>
				</div>
			</div>
			<div class="vms-cleanup-card">
				<div class="vms-cleanup-summary" id="cleanup-summary">${__("No preview loaded.")}</div>
				<div class="table-responsive"><table class="table table-bordered" id="cleanup-table"></table></div>
			</div>
			<div class="vms-cleanup-card">
				<div class="vms-cleanup-summary">${__("Cleanup History")}</div>
				<div class="table-responsive"><table class="table table-bordered" id="cleanup-history"></table></div>
			</div>
		</div>
	`);

	const fields = [
		{ fieldname: "target_doctype", fieldtype: "Select", label: __("Doctype"), options: "Visitor\nVisitor Log", default: "Visitor" },
		{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
		{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
		{ fieldname: "older_than_days", fieldtype: "Int", label: __("Older Than X Days") },
		{ fieldname: "status", fieldtype: "Data", label: __("Status / Log Status") },
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

	controls.target_doctype.$input.on("change", () => {
		state.target_doctype = controls.target_doctype.get_value() || "Visitor";
		render_table([], 0);
	});

	function get_filters() {
		return Object.fromEntries(
			Object.entries(controls)
				.filter(([key]) => key !== "target_doctype")
				.map(([key, control]) => [key, control.get_value()])
				.filter(([, value]) => value)
		);
	}

	function selected_records() {
		return $body.find(".cleanup-check:checked").map((_, el) => $(el).data("name")).get();
	}


	function column_label(column) {
		return column.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
	}

	function render_table(records, total_count) {
		state.records = records || [];
		state.count = total_count || state.records.length;
		const target = controls.target_doctype.get_value() || "Visitor";
		$body.find("#cleanup-summary").text(__("{0} {1} records match filters; showing {2} for review.", [state.count, target, state.records.length]));
		const columns = target === "Visitor Log"
			? ["name", "visitor", "action", "status", "gate", "action_time", "modified"]
			: ["name", "visitor_name", "visitor_company", "status", "check_in_time", "check_out_time", "modified"];
		$body.find("#cleanup-table").html(`
			<thead><tr><th></th>${columns.map((column) => `<th>${column_label(column)}</th>`).join("")}</tr></thead>
			<tbody>${state.records.map((row) => `
				<tr>
					<td><input type="checkbox" class="cleanup-check" data-name="${frappe.utils.escape_html(row.name)}"></td>
					${columns.map((column) => `<td>${frappe.utils.escape_html(row[column] || "")}</td>`).join("")}
				</tr>`).join("")}</tbody>
		`);
	}

	function render_history(rows) {
		$body.find("#cleanup-history").html(`
			<thead><tr><th>${__("Date")}</th><th>${__("Action")}</th><th>${__("Target")}</th><th>${__("Method")}</th><th>${__("Total")}</th><th>${__("Performed By")}</th><th>${__("Filter")}</th></tr></thead>
			<tbody>${(rows || []).map((row) => `
				<tr>
					<td>${frappe.utils.escape_html(row.performed_at || "")}</td>
					<td>${frappe.utils.escape_html(row.cleanup_action || "")}</td>
					<td>${frappe.utils.escape_html(row.target_doctype || "")}</td>
					<td>${frappe.utils.escape_html(row.cleanup_method || "")}</td>
					<td>${frappe.utils.escape_html(row.total_records || 0)}</td>
					<td>${frappe.utils.escape_html(row.performed_by || "")}</td>
					<td>${frappe.utils.escape_html(row.filter_summary || "")}</td>
				</tr>`).join("")}</tbody>
		`);
	}

	function preview() {
		const target = controls.target_doctype.get_value() || "Visitor";
		frappe.call({
			method: "visitor_management.visitor_management.maintenance.preview_cleanup_records",
			args: { target_doctype: target, filters: get_filters(), limit: 200 },
			freeze: true,
			callback: (r) => render_table((r.message && r.message.records) || [], (r.message && r.message.count) || 0),
		});
	}

	function load_history() {
		frappe.call({
			method: "visitor_management.visitor_management.maintenance.get_cleanup_history",
			args: { limit: 20 },
			callback: (r) => render_history(r.message || []),
		});
	}

	function run({ use_filtered = false, dry_run = false, background = false } = {}) {
		const names = use_filtered ? [] : selected_records();
		if (!use_filtered && !names.length) {
			frappe.msgprint(__("Select at least one record from the preview table."));
			return;
		}
		const target = controls.target_doctype.get_value() || "Visitor";
		const label = use_filtered ? __("all records matching current filters") : __("{0} selected records", [names.length]);
		const method = background
			? "visitor_management.visitor_management.maintenance.enqueue_cleanup"
			: "visitor_management.visitor_management.maintenance.run_cleanup";
		const execute = (values = {}) => {
			frappe.confirm(__("Run {0} for {1}?", [dry_run ? __("Dry Run") : __("Delete"), label]), () => {
				frappe.call({
					method,
					args: {
						target_doctype: target,
						action: "Delete",
						records: names,
						filters: get_filters(),
						confirm_text: values.confirm_text,
						dry_run: dry_run ? 1 : 0,
						cleanup_method: use_filtered ? "All Filtered Records" : "Selected Records",
					},
					freeze: true,
					callback: (r) => {
						frappe.msgprint((r.message && r.message.message) || __("Cleanup completed."));
						preview();
						load_history();
					},
				});
			});
		};
		if (!dry_run) {
			frappe.prompt([{ fieldname: "confirm_text", fieldtype: "Data", label: __("Type DELETE to confirm"), reqd: 1 }], execute, __("Confirm Delete"), __("Delete"));
		} else {
			execute();
		}
	}

	$body.find("#cleanup-preview").on("click", preview);
	$body.find("#cleanup-select-all").on("click", () => $body.find(".cleanup-check").prop("checked", true));
	$body.find("#cleanup-dry-run").on("click", () => run({ use_filtered: true, dry_run: true }));
	$body.find("#cleanup-delete-selected").on("click", () => run());
	$body.find("#cleanup-delete-filtered").on("click", () => run({ use_filtered: true }));
	$body.find("#cleanup-background").on("click", () => run({ use_filtered: true, background: true }));
	load_history();
};
