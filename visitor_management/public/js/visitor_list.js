frappe.listview_settings["Visitor"] = {
	onload(listview) {
		const filters = {
			Today: { check_in_time: ["Timespan", "today"] },
			"Checked In": { status: ["in", ["Approved", "Checked In", "Completed"]] },
			"Checked Out": { status: "Checked Out" },
			Pending: { status: "Awaiting Approval" },
			"This Month": { check_in_time: ["Timespan", "this month"] },
		};

		Object.entries(filters).forEach(([label, route_options]) => {
			listview.page.add_inner_button(__(label), () => {
				frappe.route_options = route_options;
				frappe.set_route("List", "Visitor");
				listview.refresh();
			}, __("VMS Filters"));
		});
	},
};
