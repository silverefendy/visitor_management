frappe.ui.form.on("Visitor", {
    refresh(frm) {
        frm.trigger("setup_status_indicator");
        frm.trigger("setup_action_buttons");
        frm.trigger("show_qr_code");
    },

    setup_status_indicator(frm) {
        const colors = {
            "Registered":        "gray",
            "Awaiting Approval":  "yellow",
            "Approved":           "blue",
            "Checked In":         "green",
            "Completed":          "purple",
            "Checked Out":        "teal",
            "Cancelled":          "red",
            "Rejected":           "red",
        };
        const color = colors[frm.doc.status] || "gray";
        frm.page.set_indicator(frm.doc.status, color);
    },

    setup_action_buttons(frm) {
        if (frm.is_new()) return;

        const status = frm.doc.status;
        const roles  = frappe.user_roles;
        const isSecurity = roles.includes("Visitor Security") || roles.includes("System Manager");
        const isEmployee  = roles.includes("Employee") || roles.includes("System Manager");

        // ── Security: Check In ─────────────────────────────────────────────
        if (status === "Registered" && isSecurity) {
            frm.add_custom_button(__("Check In (Scan QR)"), () => {
                frappe.confirm(
                    `Konfirmasi check-in untuk <b>${frm.doc.visitor_name}</b>?`,
                    () => {
                        frm.call({
                            method: "do_checkin",
                            freeze: true,
                            freeze_message: "Memproses check-in...",
                            callback(r) {
                                if (r.message && r.message.status === "success") {
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: "green",
                                    });
                                    frm.reload_doc();
                                }
                            },
                        });
                    }
                );
            }, __("Security Actions")).addClass("btn-primary");
        }

        // ── Karyawan: Approve Visit ────────────────────────────────────────
        if (status === "Awaiting Approval" && isEmployee) {
            frm.add_custom_button(__("✓ Terima Tamu"), () => {
                frappe.confirm(
                    `Apakah Anda menyetujui kunjungan dari <b>${frm.doc.visitor_name}</b>?`,
                    () => {
                        frm.call({
                            method: "approve_visit",
                            freeze: true,
                            callback(r) {
                                if (r.message?.status === "success") {
                                    frappe.show_alert({ message: r.message.message, indicator: "green" });
                                    frm.reload_doc();
                                }
                            },
                        });
                    }
                );
            }, __("Employee Actions")).addClass("btn-success");

            frm.add_custom_button(__("✗ Tolak Tamu"), () => {
                const d = new frappe.ui.Dialog({
                    title: "Tolak Kunjungan",
                    fields: [{
                        fieldtype: "Small Text",
                        fieldname: "reason",
                        label: "Alasan Penolakan",
                        reqd: 1,
                    }],
                    primary_action_label: "Tolak",
                    primary_action({ reason }) {
                        frm.call({
                            method: "reject_visit",
                            args: { reason },
                            freeze: true,
                            callback(r) {
                                if (r.message?.status === "success") {
                                    frappe.show_alert({ message: r.message.message, indicator: "red" });
                                    frm.reload_doc();
                                    d.hide();
                                }
                            },
                        });
                    },
                });
                d.show();
            }, __("Employee Actions")).addClass("btn-danger");
        }

        // ── Karyawan: End Visit ────────────────────────────────────────────
        if ((status === "Approved" || status === "Checked In") && isEmployee) {
            frm.add_custom_button(__("Selesaikan Kunjungan"), () => {
                frappe.confirm(
                    `Tandai kunjungan <b>${frm.doc.visitor_name}</b> sebagai selesai?`,
                    () => {
                        frm.call({
                            method: "end_visit",
                            freeze: true,
                            callback(r) {
                                if (r.message?.status === "success") {
                                    frappe.show_alert({ message: r.message.message, indicator: "blue" });
                                    frm.reload_doc();
                                }
                            },
                        });
                    }
                );
            }, __("Employee Actions")).addClass("btn-primary");
        }

        // ── Security: Check Out ───────────────────────────────────────────
        if (status === "Completed" && isSecurity) {
            frm.add_custom_button(__("Check Out (Scan QR)"), () => {
                frappe.confirm(
                    `Konfirmasi check-out untuk <b>${frm.doc.visitor_name}</b>?`,
                    () => {
                        frm.call({
                            method: "do_checkout",
                            freeze: true,
                            freeze_message: "Memproses check-out...",
                            callback(r) {
                                if (r.message?.status === "success") {
                                    frappe.show_alert({ message: r.message.message, indicator: "teal" });
                                    frm.reload_doc();
                                }
                            },
                        });
                    }
                );
            }, __("Security Actions")).addClass("btn-primary");
        }

        // ── Print Badge & QR ─────────────────────────────────────────────
        if (!frm.is_new() && status !== "Cancelled") {
            frm.add_custom_button(__("Print Visitor Badge"), () => {
                const url = `/api/method/visitor_management.visitor_management.api.print_visitor_badge?visitor_id=${frm.doc.name}`;
                window.open(url, "_blank");
            });
        }
    },

    show_qr_code(frm) {
        if (frm.doc.qr_code_image && !frm.is_new()) {
            // Tampilkan QR di sidebar / section khusus
            const qrHtml = `
                <div style="text-align:center; padding: 16px;">
                    <img src="${frm.doc.qr_code_image}"
                         style="width:180px; height:180px; border:1px solid #eee; border-radius:8px;"
                         alt="QR Code">
                    <p style="margin-top:8px; font-size:12px; color:#888;">
                        Scan QR ini di security
                    </p>
                    <p style="font-weight:bold; font-size:14px;">${frm.doc.name}</p>
                </div>
            `;
            // Tambahkan ke form
            if (!frm.qr_displayed) {
                frm.fields_dict.qr_code_image.$wrapper.after($(qrHtml));
                frm.qr_displayed = true;
            }
        }
    },

    host_employee(frm) {
        if (frm.doc.host_employee) {
            frappe.db.get_value(
                "Employee",
                frm.doc.host_employee,
                ["employee_name", "department", "designation"],
                (r) => {
                    frm.set_value("host_employee_name", r.employee_name);
                    frm.set_value("department", r.department);
                }
            );
        }
    },
});
