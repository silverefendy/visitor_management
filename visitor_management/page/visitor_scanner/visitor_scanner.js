frappe.pages["visitor-scanner"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "VMS Security Scanner",
		single_column: true,
	});

	// Load library QR scanner
	frappe.require(
		["https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js"],
		() => {
			new VMSScanner(page);
		},
	);
};

class VMSScanner {
	constructor(page) {
		this.page = page;
		this.mode = "checkin"; // 'checkin' | 'checkout'
		this.scanner = null;
		this.scanning = false;
		this.pendingVisitor = null;

		this.render();
		this.startScanner();
		this.loadActiveVisitors();

		// Refresh active visitors setiap 30 detik
		this.refreshInterval = setInterval(() => this.loadActiveVisitors(), 30000);

		// Dengar realtime event dari server
		frappe.realtime.on("vms_visitor_approved", (data) => {
			frappe.show_alert(
				{
					message: `✓ ${data.visitor_name} diizinkan masuk`,
					indicator: "green",
				},
				8,
			);
			this.loadActiveVisitors();
		});

		frappe.realtime.on("vms_visitor_rejected", (data) => {
			frappe.show_alert(
				{
					message: `✗ ${data.visitor_name} ditolak: ${data.reason || "-"}`,
					indicator: "red",
				},
				8,
			);
		});
	}

	render() {
		this.page.main.html(`
            <style>
                .vms-scanner-wrapper { max-width: 900px; margin: 0 auto; padding: 20px; }
                .mode-selector { display: flex; gap: 12px; margin-bottom: 24px; }
                .mode-btn {
                    flex: 1; padding: 14px; font-size: 16px; font-weight: bold;
                    border: 2px solid #ddd; border-radius: 8px; cursor: pointer;
                    background: #f5f5f5; transition: all 0.2s;
                }
                .mode-btn.active.checkin-mode  { background: #27ae60; color: white; border-color: #27ae60; }
                .mode-btn.active.checkout-mode { background: #2980b9; color: white; border-color: #2980b9; }
                .scanner-container { display: flex; gap: 20px; flex-wrap: wrap; }
                #qr-reader { width: 350px; min-height: 250px; border-radius: 8px; overflow: hidden; }
                .manual-input { flex: 1; min-width: 280px; }
                .manual-input input {
                    width: 100%; padding: 12px; font-size: 15px;
                    border: 2px solid #ddd; border-radius: 8px; box-sizing: border-box;
                }
                .manual-input button {
                    margin-top: 10px; width: 100%; padding: 12px;
                    background: #2e4057; color: white; border: none;
                    border-radius: 8px; font-size: 15px; cursor: pointer;
                }
                .visitor-card {
                    background: #fff; border: 1px solid #e0e0e0;
                    border-radius: 12px; padding: 20px; margin-top: 20px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }
                .visitor-card h3 { margin: 0 0 12px 0; color: #2e4057; }
                .visitor-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
                .info-item { font-size: 14px; }
                .info-label { color: #888; font-size: 12px; }
                .info-value { font-weight: 500; }
                .status-badge {
                    display: inline-block; padding: 4px 12px;
                    border-radius: 20px; font-size: 12px; font-weight: bold;
                    margin-bottom: 12px;
                }
                .action-buttons { display: flex; gap: 12px; margin-top: 16px; }
                .btn-confirm {
                    flex: 2; padding: 14px; background: #27ae60;
                    color: white; border: none; border-radius: 8px;
                    font-size: 16px; cursor: pointer; font-weight: bold;
                }
                .btn-cancel {
                    flex: 1; padding: 14px; background: #e74c3c;
                    color: white; border: none; border-radius: 8px;
                    font-size: 16px; cursor: pointer;
                }
                .result-msg {
                    padding: 16px; border-radius: 8px; margin-top: 16px;
                    font-size: 16px; text-align: center; font-weight: bold;
                }
                .result-success { background: #d5f4e6; color: #1a7a4a; }
                .result-error   { background: #fde8e8; color: #c0392b; }
                .active-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
                .active-table th {
                    background: #2e4057; color: white;
                    padding: 10px 12px; text-align: left; font-size: 13px;
                }
                .active-table td {
                    padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px;
                }
                .active-table tr:hover { background: #f8f9fa; }
            </style>

            <div class="vms-scanner-wrapper">
                <div class="mode-selector">
                    <button class="mode-btn active checkin-mode" id="btn-checkin"
                            onclick="window.vmsScanner.setMode('checkin')">
                        ▶ CHECK IN
                    </button>
                    <button class="mode-btn checkout-mode" id="btn-checkout"
                            onclick="window.vmsScanner.setMode('checkout')">
                        ◀ CHECK OUT
                    </button>
                </div>

                <div class="scanner-container">
                    <div id="qr-reader"></div>
                    <div class="manual-input">
                        <p style="color:#888; margin-top:0;">— atau input manual —</p>
                        <input type="text" id="manual-visitor-id"
                               placeholder="Ketik Visitor ID (VIS-2024-01-0001)"
                               onkeydown="if(event.key==='Enter') window.vmsScanner.processManualInput()">
                        <button onclick="window.vmsScanner.processManualInput()">
                            Proses Manual
                        </button>
                        <div id="result-message"></div>
                    </div>
                </div>

                <div id="visitor-card" style="display:none;" class="visitor-card">
                    <div id="visitor-card-content"></div>
                    <div class="action-buttons">
                        <button class="btn-confirm" id="btn-confirm"
                                onclick="window.vmsScanner.confirmAction()">
                            ✓ KONFIRMASI
                        </button>
                        <button class="btn-cancel" onclick="window.vmsScanner.resetCard()">
                            ✗ Batal
                        </button>
                    </div>
                </div>

                <div style="margin-top: 32px;">
                    <h3 style="color:#2e4057;">Tamu Aktif Saat Ini</h3>
                    <div id="active-visitors-list"></div>
                </div>
            </div>
        `);

		// Simpan reference global agar bisa dipanggil dari inline onclick
		window.vmsScanner = this;
	}

	setMode(mode) {
		this.mode = mode;
		const btnCI = document.getElementById("btn-checkin");
		const btnCO = document.getElementById("btn-checkout");

		if (mode === "checkin") {
			btnCI.classList.add("active");
			btnCO.classList.remove("active");
		} else {
			btnCO.classList.add("active");
			btnCI.classList.remove("active");
		}
		this.resetCard();
	}

	startScanner() {
		if (!window.Html5QrcodeScanner) return;

		this.scanner = new Html5QrcodeScanner("qr-reader", {
			fps: 10,
			qrbox: { width: 250, height: 250 },
			rememberLastUsedCamera: true,
		});

		this.scanner.render(
			(decodedText) => this.onQRScanned(decodedText),
			(error) => {
				/* ignore scan errors */
			},
		);
	}

	onQRScanned(qrData) {
		if (this.scanning) return;
		this.scanning = true;

		this.fetchVisitorInfo(qrData)
			.then((visitor) => {
				this.pendingVisitor = { qrData, visitor };
				this.showVisitorCard(visitor);
			})
			.catch((err) => {
				this.showResult("error", `QR tidak valid: ${err.message || err}`);
				setTimeout(() => {
					this.scanning = false;
				}, 3000);
			});
	}

	processManualInput() {
		const input = document.getElementById("manual-visitor-id");
		const visitorId = input.value.trim();
		if (!visitorId) {
			frappe.show_alert({ message: "Masukkan Visitor ID", indicator: "orange" });
			return;
		}

		// Buat QR data dari manual input
		const qrData = JSON.stringify({ visitor_id: visitorId });
		this.onQRScanned(qrData);
	}

	fetchVisitorInfo(qrData) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "visitor_management.visitor_management.api.get_visitor_by_qr",
				args: { qr_data: qrData },
				callback(r) {
					if (r.message && !r.message.error) {
						resolve(r.message);
					} else {
						reject(new Error(r.message?.error || "Visitor tidak ditemukan"));
					}
				},
				error(err) {
					reject(err);
				},
			});
		});
	}

	showVisitorCard(v) {
		const statusColors = {
			Registered: "#95a5a6",
			"Awaiting Approval": "#f39c12",
			Approved: "#3498db",
			"Checked In": "#27ae60",
			Completed: "#9b59b6",
			"Checked Out": "#1abc9c",
			Rejected: "#e74c3c",
			Cancelled: "#e74c3c",
		};

		const color = statusColors[v.status] || "#888";
		const canCheckin = ["Registered", "Approved"].includes(v.status);
		const canCheckout = v.status === "Completed";
		const modeLabel = this.mode === "checkin" ? "CHECK IN" : "CHECK OUT";

		const canProceed = this.mode === "checkin" ? canCheckin : canCheckout;
		const btnText = canProceed
			? `✓ Konfirmasi ${modeLabel}`
			: `⚠ Tidak dapat ${modeLabel} (Status: ${v.status})`;

		document.getElementById("visitor-card-content").innerHTML = `
            <h3>${v.visitor_name}</h3>
            <span class="status-badge" style="background:${color}20; color:${color}; border:1px solid ${color};">
                ${v.status}
            </span>
            <div class="visitor-info-grid">
                <div class="info-item">
                    <div class="info-label">Perusahaan</div>
                    <div class="info-value">${v.visitor_company || "-"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Host</div>
                    <div class="info-value">${v.host_employee_name}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Departemen</div>
                    <div class="info-value">${v.department || "-"}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Keperluan</div>
                    <div class="info-value">${v.visit_purpose}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Identitas</div>
                    <div class="info-value">${v.id_type}: ${v.id_number}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Check In</div>
                    <div class="info-value">${v.check_in_time || "-"}</div>
                </div>
            </div>
        `;

		const btnConfirm = document.getElementById("btn-confirm");
		btnConfirm.textContent = btnText;
		btnConfirm.disabled = !canProceed;
		btnConfirm.style.opacity = canProceed ? "1" : "0.5";

		document.getElementById("visitor-card").style.display = "block";
		document.getElementById("visitor-card").scrollIntoView({ behavior: "smooth" });
	}

	confirmAction() {
		if (!this.pendingVisitor) return;

		const { qrData } = this.pendingVisitor;

		frappe.call({
			method: "visitor_management.visitor_management.api.scan_qr_action",
			args: {
				qr_data: qrData,
				action: this.mode,
			},
			freeze: true,
			freeze_message: "Memproses...",
			callback: (r) => {
				if (r.message?.status === "success") {
					this.showResult("success", r.message.message);
					this.loadActiveVisitors();
					setTimeout(() => this.resetAll(), 4000);
				}
			},
			error: (err) => {
				this.showResult("error", err.message || "Gagal memproses");
				setTimeout(() => this.resetCard(), 3000);
			},
		});
	}

	showResult(type, message) {
		const el = document.getElementById("result-message");
		el.className = `result-msg result-${type}`;
		el.textContent = message;
		el.style.display = "block";
		setTimeout(() => {
			el.style.display = "none";
		}, 5000);
	}

	resetCard() {
		this.pendingVisitor = null;
		this.scanning = false;
		document.getElementById("visitor-card").style.display = "none";
		document.getElementById("manual-visitor-id").value = "";
	}

	resetAll() {
		this.resetCard();
		document.getElementById("result-message").style.display = "none";
	}

	loadActiveVisitors() {
		frappe.call({
			method: "visitor_management.visitor_management.api.get_dashboard_data",
			callback: (r) => {
				if (!r.message) return;
				const { active_visitors, stats } = r.message;
				const el = document.getElementById("active-visitors-list");

				if (!active_visitors.length) {
					el.innerHTML = `<p style="color:#aaa; text-align:center; padding:20px;">
                        Tidak ada tamu aktif saat ini</p>`;
					return;
				}

				const rows = active_visitors
					.map(
						(v) => `
                    <tr>
                        <td><strong>${v.visitor_name}</strong><br>
                            <span style="font-size:11px; color:#888;">${v.visitor_company || "-"}</span>
                        </td>
                        <td>${v.host_employee_name}<br>
                            <span style="font-size:11px; color:#888;">${v.department || "-"}</span>
                        </td>
                        <td>${v.check_in_time ? frappe.datetime.str_to_user(v.check_in_time) : "-"}</td>
                        <td>
                            <span style="
                                padding:3px 10px; border-radius:12px; font-size:11px;
                                background:${v.status === "Awaiting Approval" ? "#fff3cd" : "#d5f4e6"};
                                color:${v.status === "Awaiting Approval" ? "#856404" : "#1a7a4a"};
                            ">${v.status}</span>
                        </td>
                    </tr>
                `,
					)
					.join("");

				el.innerHTML = `
                    <table class="active-table">
                        <thead>
                            <tr>
                                <th>Nama Tamu</th>
                                <th>Host</th>
                                <th>Check In</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                    <p style="font-size:12px; color:#aaa; margin-top:8px; text-align:right;">
                        Total hari ini: ${stats.total_today} kunjungan
                        | Aktif: ${stats.checked_in}
                        | Selesai: ${stats.checked_out}
                    </p>
                `;
			},
		});
	}
}
