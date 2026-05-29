(function () {
	const ACTIVE_VISITOR_STATUSES = ["Awaiting Approval", "Approved", "Completed", "Checked In"];
	const VMS_COMMANDS = [
		{
			label: "New Visitor",
			keywords: ["new visitor", "visitor baru", "register visitor", "add visitor", "tamu baru"],
			action: () => frappe.new_doc("Visitor"),
		},
		{
			label: "Visitor List",
			keywords: ["visitor", "visitor list", "visitors", "daftar visitor", "daftar tamu"],
			action: () => frappe.set_route("List", "Visitor"),
		},
		{
			label: "Scan QR",
			keywords: ["scan qr", "qr scan", "scanner", "scan visitor", "scan tamu", "barcode"],
			action: () => {
				window.location.href = "/vms-scanner";
			},
		},
		{
			label: "Check In",
			keywords: ["check in", "checkin", "visitor check in", "tamu masuk"],
			action: () => {
				window.location.href = "/vms-scanner?intent=check-in";
			},
		},
		{
			label: "Check Out",
			keywords: ["check out", "checkout", "visitor check out", "tamu keluar"],
			action: () => {
				window.location.href = "/vms-scanner?intent=check-out";
			},
		},
		{
			label: "Visitor Today",
			keywords: ["visitor today", "today visitors", "visitors today", "tamu hari ini"],
			action: () => open_visitor_list({ check_in_time: ["Timespan", "today"] }),
		},
		{
			label: "Checked In Visitors",
			keywords: ["checked in", "active visitors", "visitor active", "currently checked in", "tamu aktif"],
			action: () => open_visitor_list({ status: ["in", ACTIVE_VISITOR_STATUSES] }),
		},
		{
			label: "Checked Out Visitors",
			keywords: ["checked out", "visitor checked out", "checkout visitors", "tamu keluar"],
			action: () => open_visitor_list({ status: "Checked Out" }),
		},
		{
			label: "Pending Visitors",
			keywords: ["pending visitor", "pending approval", "awaiting approval", "menunggu approval"],
			action: () => open_visitor_list({ status: "Awaiting Approval" }),
		},
		{
			label: "Visitor Logs",
			keywords: ["visitor log", "visitor logs", "history visitor", "riwayat visitor", "log tamu"],
			action: () => frappe.set_route("List", "Visitor Log"),
		},
		{
			label: "VMS Settings",
			keywords: ["vms settings", "visitor settings", "qr settings", "approval settings", "notification settings"],
			action: () => frappe.set_route("Form", "Visitor Settings"),
		},
		{
			label: "Data Cleanup",
			keywords: ["data cleanup", "cleanup visitor", "archive visitor", "delete old visitor", "maintenance"],
			action: () => frappe.set_route("vms-data-cleanup"),
		},
		{
			label: "Visitor Management Workspace",
			keywords: ["visitor management", "vms", "visitor workspace", "workspace visitor"],
			action: () => frappe.set_route("Workspaces", "Visitor Management"),
		},
	];

	function open_visitor_list(route_options) {
		frappe.route_options = route_options;
		frappe.set_route("List", "Visitor");
	}

	function normalize(value) {
		return String(value || "").toLowerCase().replace(/[\s_-]+/g, " ").trim();
	}

	function command_matches(command, keywords) {
		const term = normalize(keywords);
		if (!term) return false;
		return command.keywords.some((keyword) => {
			const candidate = normalize(keyword);
			return candidate === term || candidate.includes(term) || term.includes(candidate);
		});
	}

	function result_for(command, keywords, index) {
		const fuzzy_result = frappe.search.utils.fuzzy_search(keywords, command.label, true) || {};
		const marked = fuzzy_result.marked_string || command.label;
		return {
			type: "VMS",
			label: __("Open {0}", [marked]),
			value: command.label,
			match: command.label,
			index: 999 - index,
			onclick: command.action,
		};
	}

	function get_vms_results(keywords) {
		return VMS_COMMANDS.filter((command) => command_matches(command, keywords)).map((command, index) =>
			result_for(command, keywords, index)
		);
	}

	function install() {
		if (
			!frappe.search ||
			!frappe.search.utils ||
			!frappe.search.utils.get_nav_results ||
			!frappe.search.utils.make_function_searchable ||
			frappe.search.utils.__vms_navigation_installed
		) {
			return;
		}

		frappe.search.utils.__vms_navigation_installed = true;
		VMS_COMMANDS.forEach((command) => {
			frappe.search.utils.make_function_searchable(command.action, command.label);
		});

		const original_get_nav_results = frappe.search.utils.get_nav_results.bind(frappe.search.utils);
		frappe.search.utils.get_nav_results = function (keywords) {
			const result_sets = original_get_nav_results(keywords);
			const vms_results = get_vms_results(keywords);

			if (vms_results.length) {
				result_sets.unshift({
					title: __("Visitor Management Shortcuts"),
					fetch_type: "Nav",
					results: vms_results,
				});
			}

			return result_sets;
		};
	}

	frappe.ready(() => {
		install();
		setTimeout(install, 1000);
	});
})();
