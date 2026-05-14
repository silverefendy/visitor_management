frappe.ui.form.on("Visitor", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === "Awaiting Approval") {
			frm.add_custom_button(__("Approve"), () => {
				frm.call("approve_visit").then((r) => {
					if (r.message)
						frappe.msgprint(r.message.message || __("Kunjungan disetujui."));
					frm.reload_doc();
				});
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
					(values) => {
						frm.call("reject_visit", { reason: values.reason }).then((r) => {
							if (r.message)
								frappe.msgprint(r.message.message || __("Kunjungan ditolak."));
							frm.reload_doc();
						});
					},
					__("Reject Visit"),
					__("Reject"),
				);
			});
		}

		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Selesai Kunjungan"), () => {
				frappe.confirm(
					__(
						"Tandai kunjungan ini selesai? Setelah itu security dapat melakukan check-out.",
					),
					() => {
						frm.call("end_visit").then((r) => {
							if (r.message)
								frappe.msgprint(r.message.message || __("Kunjungan selesai."));
							frm.reload_doc();
						});
					},
				);
			}).addClass("btn-primary");
		}
	},
});
