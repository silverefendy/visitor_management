frappe.ui.form.on("Visitor", {
	refresh(frm) {
		render_visitor_preview(frm);

		if (frm.is_new()) return;

		if (frm.doc.status === "Awaiting Approval") {
			frm.add_custom_button(__("Approve"), () => {
				frm.call("approve_visit").then((r) => {
					if (r.message) frappe.msgprint(r.message.message || __("Kunjungan disetujui."));
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
							if (r.message) frappe.msgprint(r.message.message || __("Kunjungan ditolak."));
							frm.reload_doc();
						});
					},
					__("Reject Visit"),
					__("Reject")
				);
			});
		}

		if (["Approved", "Checked In", "Completed"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Check Out"), () => {
				frappe.confirm(__("Check out this visitor now?"), () => {
					frm.call("do_checkout").then((r) => {
						if (r.message) frappe.msgprint(r.message.message || __("Visitor checked out."));
						frm.reload_doc();
					});
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Selesai Kunjungan"), () => {
				frappe.confirm(__("Tandai kunjungan ini selesai?"), () => {
					frm.call("end_visit").then((r) => {
						if (r.message) frappe.msgprint(r.message.message || __("Kunjungan selesai."));
						frm.reload_doc();
					});
				});
			});
		}

		if (!["Archived"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Archive"), () => {
				frappe.confirm(__("Archive this visitor record?"), () => {
					frm.call("archive_visit").then((r) => {
						if (r.message) frappe.msgprint(r.message.message || __("Visitor archived."));
						frm.reload_doc();
					});
				});
			}, __("Actions"));
		}
	},

	visitor_name: render_visitor_preview,
	visitor_company: render_visitor_preview,
	status: render_visitor_preview,
	check_in_time: render_visitor_preview,
	check_out_time: render_visitor_preview,
	visitor_photo: render_visitor_preview,
	qr_code_image: render_visitor_preview,
});

function render_visitor_preview(frm) {
	if (window.visitor_management && window.visitor_management.visitor_preview) {
		window.visitor_management.visitor_preview.render(frm);
	}
}
