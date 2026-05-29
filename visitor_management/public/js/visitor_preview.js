(function () {
	const IMAGE_EXTENSIONS = /\.(png|jpe?g|webp|gif|svg)(\?.*)?$/i;
	const QR_PATTERN = /(^|[\s_\-\/])qr([\s_\-\.]|$)|qrcode|qr_code/i;
	const STATUS_STYLES = {
		"Checked In": "checked-in",
		Approved: "checked-in",
		Completed: "completed",
		"Checked Out": "checked-out",
		Registered: "pending",
		"Awaiting Approval": "pending",
		Pending: "pending",
		Rejected: "cancelled",
		Cancelled: "cancelled",
	};

	function escape_html(value) {
		return frappe.utils.escape_html(value == null || value === "" ? "—" : String(value));
	}

	function status_class(status) {
		return STATUS_STYLES[status] || "pending";
	}

	function status_badge(status) {
		const label = status || __("Pending");
		return `<span class="vms-status-badge vms-status-${status_class(label)}">${escape_html(label).toUpperCase()}</span>`;
	}

	function asset_url(file_url) {
		if (!file_url) return "";
		return file_url.startsWith("http") || file_url.startsWith("/") ? file_url : `/${file_url}`;
	}

	function format_datetime(value) {
		if (!value) return "—";
		const moment_value = frappe.datetime && frappe.datetime.moment ? frappe.datetime.moment(value) : moment(value);
		const timezone = frappe.boot && (frappe.boot.time_zone || frappe.boot.sysdefaults?.time_zone);
		return `${moment_value.format("DD MMM YYYY — HH:mm")} ${timezone || ""}`.trim();
	}

	function image_card(url, label, placeholder_icon, extra_class) {
		if (url) {
			return `
				<button class="vms-image-card ${extra_class || ""}" data-vms-zoom="${escape_html(url)}" type="button" title="${escape_html(__("Click to zoom"))}">
					<img src="${escape_html(url)}" alt="${escape_html(label)}" loading="lazy" />
				</button>`;
		}

		return `
			<div class="vms-image-card vms-image-placeholder ${extra_class || ""}">
				<div class="vms-placeholder-icon">${placeholder_icon}</div>
				<div>${escape_html(label)}</div>
			</div>`;
	}

	function get_direct_images(doc) {
		return {
			photo: asset_url(doc.visitor_photo),
			qr: asset_url(doc.qr_code_image),
		};
	}

	function pick_attachment_images(files) {
		const image_files = (files || [])
			.filter((file) => IMAGE_EXTENSIONS.test(file.file_url || file.file_name || ""))
			.sort((a, b) => new Date(b.creation || b.modified || 0) - new Date(a.creation || a.modified || 0));

		const qr = image_files.find((file) => {
			const haystack = `${file.file_name || ""} ${file.file_url || ""} ${file.attached_to_field || ""}`;
			return file.attached_to_field === "qr_code_image" || QR_PATTERN.test(haystack);
		});

		const photo = image_files.find((file) => {
			const haystack = `${file.file_name || ""} ${file.file_url || ""} ${file.attached_to_field || ""}`;
			return file.attached_to_field === "visitor_photo" || !QR_PATTERN.test(haystack);
		});

		return {
			photo: asset_url(photo && photo.file_url),
			qr: asset_url(qr && qr.file_url),
		};
	}

	function get_actions(frm) {
		const actions = [
			{ label: __("Print Badge"), icon: "printer", action: () => print_badge(frm) },
			{ label: __("Reprint QR"), icon: "qr-code", action: () => regenerate_qr(frm) },
			{ label: __("View Logs"), icon: "list", action: () => view_logs(frm) },
		];

		if (frm.doc.status === "Completed") {
			actions.splice(2, 0, { label: __("Check Out"), icon: "sign-out", primary: true, action: () => checkout(frm) });
		}

		return actions;
	}

	function render_action_buttons(frm) {
		return get_actions(frm)
			.map(
				(action, index) => `
					<button class="btn btn-sm ${action.primary ? "btn-primary" : "btn-default"} vms-summary-action" data-vms-action="${index}" type="button">
						${escape_html(action.label)}
					</button>`
			)
			.join("");
	}

	function render_header(frm) {
		return `
			<div class="vms-visitor-header">
				<div class="vms-header-identity">
					<div class="vms-avatar">${escape_html((frm.doc.visitor_name || frm.doc.name || "V").charAt(0)).toUpperCase()}</div>
					<div>
						<div class="vms-eyebrow">${escape_html(__("Visitor Management"))}</div>
						<h2>${escape_html(frm.doc.visitor_name || frm.doc.name)}</h2>
						<div class="vms-header-company">${escape_html(frm.doc.visitor_company || __("No company provided"))}</div>
					</div>
				</div>
				<div class="vms-header-meta">
					${status_badge(frm.doc.status)}
					<div class="vms-header-actions">${render_action_buttons(frm)}</div>
				</div>
			</div>`;
	}

	function render_preview(frm, images) {
		return `
			<aside class="vms-preview-panel" aria-label="${escape_html(__("Visitor Preview"))}">
				<div class="vms-preview-title">
					<span>${escape_html(__("Visitor Preview"))}</span>
					${status_badge(frm.doc.status)}
				</div>
				<div class="vms-preview-media">
					${image_card(images.photo, __("No visitor photo"), "👤", "vms-photo-card")}
					${image_card(images.qr, __("No QR image"), "▦", "vms-qr-card")}
				</div>
				<div class="vms-preview-details">
					<div class="vms-detail-row"><span>${escape_html(__("Name"))}</span><strong>${escape_html(frm.doc.visitor_name || frm.doc.name)}</strong></div>
					<div class="vms-detail-row"><span>${escape_html(__("Company"))}</span><strong>${escape_html(frm.doc.visitor_company)}</strong></div>
					<div class="vms-time-grid">
						<div class="vms-time-card in"><span>🟢 ${escape_html(__("Check In"))}</span><strong>${escape_html(format_datetime(frm.doc.check_in_time))}</strong></div>
						<div class="vms-time-card out"><span>🔴 ${escape_html(__("Check Out"))}</span><strong>${escape_html(format_datetime(frm.doc.check_out_time))}</strong></div>
					</div>
				</div>
			</aside>`;
	}

	function ensure_shell(frm) {
		const $layout = frm.$wrapper.find(".form-layout").first();
		if (!$layout.length) return null;

		$layout.addClass("vms-form-layout");
		$layout.find("> .vms-visitor-header, > .vms-preview-panel").remove();
		$layout.prepend(render_header(frm));
		return $layout;
	}

	function bind_events(frm) {
		const actions = get_actions(frm);
		frm.$wrapper.find(".vms-summary-action").off("click.vms").on("click.vms", function () {
			const action = actions[Number($(this).attr("data-vms-action"))];
			if (action && action.action) action.action();
		});

		frm.$wrapper.find("[data-vms-zoom]").off("click.vms").on("click.vms", function () {
			const url = $(this).attr("data-vms-zoom");
			frappe.msgprint({
				title: __("Visitor Image"),
				message: `<div class="vms-zoom-modal"><img src="${escape_html(url)}" alt="${escape_html(__("Visitor image"))}" /></div>`,
				wide: true,
			});
		});
	}

	function print_badge(frm) {
		const panel = frm.$wrapper.find(".vms-preview-panel").first().clone();
		const print_window = window.open("", "_blank");
		print_window.document.write(`<!doctype html><html><head><title>${escape_html(frm.doc.visitor_name || frm.doc.name)}</title><link rel="stylesheet" href="/assets/visitor_management/css/visitor_custom.css"></head><body class="vms-print-body">${panel.prop("outerHTML")}</body></html>`);
		print_window.document.close();
		print_window.focus();
		setTimeout(() => print_window.print(), 250);
	}

	function regenerate_qr(frm) {
		frappe.confirm(__("Regenerate and reprint this visitor QR code?"), () => {
			frm.call("generate_qr_code").then(() => frm.reload_doc());
		});
	}

	function checkout(frm) {
		frappe.confirm(__("Check out this visitor now?"), () => {
			frm.call("do_checkout").then((r) => {
				if (r.message) frappe.msgprint(r.message.message || __("Visitor checked out."));
				frm.reload_doc();
			});
		});
	}

	function view_logs(frm) {
		frappe.set_route("List", "Visitor Log", { visitor: frm.doc.name });
	}

	async function load_attachment_images(frm) {
		if (frm.is_new()) return get_direct_images(frm.doc);

		const direct = get_direct_images(frm.doc);
		try {
			const response = await frappe.db.get_list("File", {
				fields: ["file_name", "file_url", "attached_to_field", "creation", "modified"],
				filters: {
					attached_to_doctype: frm.doctype,
					attached_to_name: frm.doc.name,
				},
				order_by: "creation desc",
				limit: 50,
			});
			const detected = pick_attachment_images(response);
			return {
				photo: direct.photo || detected.photo,
				qr: detected.qr || direct.qr,
			};
		} catch (error) {
			console.warn("Unable to load Visitor attachments", error);
			return direct;
		}
	}

	async function render(frm) {
		const $layout = ensure_shell(frm);
		if (!$layout) return;

		const images = await load_attachment_images(frm);
		$layout.find("> .vms-preview-panel").remove();
		$layout.append(render_preview(frm, images));
		bind_events(frm);
	}

	window.visitor_management = window.visitor_management || {};
	window.visitor_management.visitor_preview = {
		render,
		status_badge,
	};
})();
