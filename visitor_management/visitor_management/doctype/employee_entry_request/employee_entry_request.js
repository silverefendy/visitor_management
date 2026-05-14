frappe.ui.form.on("Employee Entry Request", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("Approve"), () => {
				frm.call("approve").then(() => frm.reload_doc());
			}).addClass("btn-primary");

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Alasan Penolakan"),
							reqd: 1,
						},
					],
					(values) =>
						frm.call("reject", { reason: values.reason }).then(() => frm.reload_doc()),
					__("Reject Employee Entry"),
					__("Reject"),
				);
			});
		}

		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Selesai"), () => {
				frm.call("complete").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Completed") {
			frm.add_custom_button(__("Check Out"), () => {
				frm.call("checkout").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}
	},
});
