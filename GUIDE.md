# Visitor Management Guide

Panduan ini dibuat dari hasil pengecekan file di repo `visitor_management-main`.
Project ini adalah aplikasi Frappe/ERPNext untuk mencatat tamu, membuat QR code,
melakukan check-in/check-out lewat scanner, serta menyimpan log aktivitas visitor.

## Ringkasan Aplikasi

- Nama app: `visitor_management`
- Framework: Frappe/ERPNext
- Publisher: FnD Corp
- Modul utama: `Visitor Management`
- Doctype utama: `Visitor`
- Doctype log: `Visitor Log`
- Halaman scanner: `visitor-scanner` dan `www/vms-scanner.html`
- Bahasa utama UI/custom message: Indonesia

## Struktur File Penting

```text
.
|-- README.md
|-- pyproject.toml
|-- setup.py
|-- .pre-commit-config.yaml
|-- .github/workflows/
|   |-- ci.yml
|   `-- linter.yml
`-- visitor_management/
    |-- hooks.py
    |-- api.py
    |-- modules.txt
    |-- patches.txt
    |-- page/visitor_scanner/
    |   |-- visitor_scanner.html
    |   |-- visitor_scanner.js
    |   `-- visitor_scanner.json
    |-- www/vms-scanner.html
    `-- visitor_management/
        |-- api.py
        |-- doctype/
        |   |-- visitor/
        |   |   |-- visitor.json
        |   |   |-- visitor.py
        |   |   |-- visitor.js
        |   |   `-- test_visitor.py
        |   `-- visitor_log/
        |       |-- visitor_log.json
        |       |-- visitor_log.py
        |       |-- visitor_log.js
        |       `-- test_visitor_log.py
        `-- workspace/visitor_management/visitor_management.json
```

Catatan: ada beberapa file doctype dan API yang muncul pada dua lokasi:

- `visitor_management/api.py`
- `visitor_management/visitor_management/api.py`
- `visitor_management/doctype/...`
- `visitor_management/visitor_management/doctype/...`

Untuk pemanggilan method dari UI, file yang aktif dipakai saat ini adalah path
`visitor_management.visitor_management.api`.

## Instalasi di Frappe Bench

Jalankan dari folder bench:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench --site nama_site install-app visitor_management
bench --site nama_site migrate
bench build
bench restart
```

Jika app sudah berada di folder `apps/visitor_management`, cukup jalankan:

```bash
bench --site nama_site install-app visitor_management
bench --site nama_site migrate
```

## Dependency yang Perlu Dicek

Kode `visitor.py` memakai library Python:

```python
qrcode
```

Namun repo ini belum terlihat memiliki file `requirements.txt`, sementara
`setup.py` membaca file tersebut:

```python
with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")
```

Saran:

1. Tambahkan `requirements.txt` berisi dependency yang benar, misalnya `qrcode`.
2. Atau pindahkan dependency ke `pyproject.toml` sesuai standar packaging yang dipakai.
3. Pastikan dependency image backend untuk QR code tersedia jika dibutuhkan, misalnya `pillow`.

## Doctype Visitor

File utama:

- `visitor_management/visitor_management/doctype/visitor/visitor.json`
- `visitor_management/visitor_management/doctype/visitor/visitor.py`

Naming:

```text
VIS-{YYYY}-{MM}-{#####}
```

Field penting:

- `visitor_name`: nama tamu, wajib
- `visitor_phone`: nomor telepon, wajib
- `visitor_email`: email
- `visitor_company`: perusahaan
- `id_type`: jenis ID, wajib
- `id_number`: nomor ID, wajib
- `visit_purpose`: keperluan kunjungan, wajib
- `host_employee`: karyawan yang dituju, wajib
- `host_employee_name`: otomatis dari Employee
- `department`: otomatis dari Employee
- `status`: status alur visitor
- `check_in_time`: waktu check-in
- `check_out_time`: waktu check-out
- `approved_by`: user yang approve/reject
- `approved_at`: waktu approval/reject
- `rejected_reason`: alasan penolakan
- `qr_code`: data QR dalam format JSON
- `qr_code_image`: gambar QR
- `visitor_photo`: foto tamu
- `notes`: catatan tambahan

Status yang tersedia:

```text
Registered
Awaiting Approval
Approved
Completed
Checked Out
Rejected
Cancelled
```

## Alur Visitor

Alur dasar yang terbaca dari controller:

1. Security atau admin membuat dokumen `Visitor`.
2. Saat dokumen dibuat, sistem set status menjadi `Registered`.
3. Setelah insert/save, sistem membuat QR code.
4. Security scan QR untuk check-in.
5. Status berubah menjadi `Awaiting Approval`.
6. Karyawan/host menyetujui atau menolak.
7. Jika disetujui, status menjadi `Approved`.
8. Saat kunjungan selesai, method `end_visit` mengubah status menjadi `Completed`.
9. Security scan QR untuk checkout.
10. Status menjadi `Checked Out`.

## Method Penting di Visitor

Di `visitor.py`:

- `before_insert()`: set status awal ke `Registered`.
- `after_insert()`: generate QR code.
- `after_save()`: generate QR code jika belum ada gambar QR.
- `validate()`: memastikan `host_employee` masih aktif.
- `generate_qr_code()`: membuat file QR dan attach ke Visitor.
- `do_checkin()`: check-in visitor dan buat log.
- `approve_visit()`: approve kunjungan.
- `reject_visit(reason="")`: reject kunjungan.
- `end_visit()`: menandai kunjungan selesai.
- `do_checkout()`: check-out visitor.
- `create_visitor_log(action, remarks="")`: membuat record `Visitor Log`.

## Doctype Visitor Log

File utama:

- `visitor_management/visitor_management/doctype/visitor_log/visitor_log.json`
- `visitor_management/visitor_management/doctype/visitor_log/visitor_log.py`

Naming:

```text
VL-{YYYY}-{MM}-{#####}
```

Field penting:

- `visitor`: link ke doctype Visitor
- `action`: aksi yang terjadi
- `action_time`: waktu aksi
- `action_by`: user yang melakukan aksi
- `remarks`: keterangan

Action yang tersedia:

```text
Check In
Approved
Rejected
Completed
Check Out
Cancelled
```

Controller `VisitorLog.before_insert()` otomatis mengisi:

- `action_time` dengan waktu sekarang jika kosong
- `action_by` dengan user session jika kosong

## API Whitelisted

File aktif:

```text
visitor_management/visitor_management/api.py
```

Method yang tersedia:

- `scan_qr_action(qr_data, action)`
  - Endpoint utama scanner.
  - `action` dapat bernilai `checkin` atau `checkout`.
  - Menerima QR JSON atau langsung Visitor ID.

- `get_visitor_by_qr(qr_data)`
  - Mengambil detail visitor untuk preview sebelum konfirmasi.

- `get_dashboard_data()`
  - Mengambil statistik visitor hari ini dan daftar visitor aktif.

- `employee_pending_approvals()`
  - Mengambil visitor yang menunggu approval untuk employee user login.

- `print_visitor_badge(visitor_id)`
  - Menghasilkan HTML badge visitor.

- `get_visitor_report(from_date, to_date, department=None, status=None)`
  - Menghasilkan daftar visitor pada periode tertentu.

## Halaman Scanner

Ada dua bentuk scanner:

1. Desk Page:
   - `visitor_management/page/visitor_scanner/visitor_scanner.json`
   - `visitor_management/page/visitor_scanner/visitor_scanner.js`
   - `visitor_management/page/visitor_scanner/visitor_scanner.html`

2. Web page statis:
   - `visitor_management/www/vms-scanner.html`

Scanner memakai library CDN:

```text
https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js
```

Fitur scanner:

- Mode check-in dan check-out.
- Scan QR lewat kamera.
- Input manual Visitor ID.
- Preview data visitor sebelum konfirmasi.
- Tabel visitor aktif.
- Refresh daftar visitor aktif.

## Role dan Permission

Dari JSON doctype dan workspace, role yang dipakai:

- `System Manager`
- `Visitor Manager`
- `Visitor Security`
- `Employee`

Hak akses Visitor:

- `System Manager`: akses penuh.
- `Visitor Manager`: create, read, write, report, export, print, email, share.
- `Visitor Security`: read, write, report, export, print, email, share.
- `Employee`: read, write, report, export, print, email, share.

Hak akses Visitor Log:

- `System Manager`: akses penuh.
- `Visitor Manager`: create, read, report, export, print, email, share.
- `Visitor Security`: read, report, export, print, email, share.

## Workspace

Workspace tersedia di:

```text
visitor_management/visitor_management/workspace/visitor_management/visitor_management.json
```

Workspace menampilkan shortcut:

- Visitor
- Visitor Log

Role workspace:

- System Manager
- Visitor Manager
- Visitor Security
- Employee

## CI dan Linting

Workflow GitHub Actions:

- `.github/workflows/ci.yml`
  - Setup Redis, MariaDB, Python 3.14, Node 24.
  - Install Frappe bench.
  - Install app.
  - Run test app.

- `.github/workflows/linter.yml`
  - Run pre-commit.
  - Run Semgrep rules Frappe.
  - Run `pip-audit`.

Pre-commit memakai:

- trailing whitespace check
- merge conflict check
- AST/JSON/TOML/YAML check
- Ruff import sorter
- Ruff linter
- Ruff formatter
- Prettier
- ESLint

## Testing

Test skeleton ada di:

- `visitor_management/visitor_management/doctype/visitor/test_visitor.py`
- `visitor_management/visitor_management/doctype/visitor_log/test_visitor_log.py`

Saat ini kedua test class masih `pass`, jadi belum ada assertion bisnis.

Jalankan test dari bench:

```bash
bench --site nama_site set-config allow_tests true
bench --site nama_site run-tests --app visitor_management
```

## Catatan Teknis yang Perlu Diperhatikan

1. `setup.py` membaca `requirements.txt`, tetapi file tersebut belum ada di repo.
2. `pyproject.toml` memakai `requires-python = ">=3.14"` dan Ruff target `py314`; pastikan environment memang Python 3.14.
3. QR code disimpan ke path hardcoded:

   ```text
   /home/frappe/frappe-bench-v16/sites/wp.local/public/files
   ```

   Ini bisa gagal jika site name, bench path, atau environment berbeda. Lebih aman memakai API file manager Frappe atau path site dinamis.

4. Ada struktur file yang tampak duplikat di root package dan subpackage. Pastikan hanya satu lokasi yang menjadi sumber utama agar maintenance tidak bercabang.
5. Beberapa teks UI tampak encoding rusak, misalnya simbol check/print menjadi karakter seperti `âœ“`. Jika UI terlihat aneh, perbaiki encoding file ke UTF-8.
6. Method `print_visitor_badge()` mengimpor `RespondAsWebsocket`, tetapi import tersebut tidak dipakai.
7. Status scanner check-out hanya mengizinkan status `Completed`. Jadi sebelum checkout, host atau operator perlu menjalankan `end_visit()`.
8. `get_dashboard_data()` menghitung `checked_in` sebagai status `Checked In` dan `Approved`, tetapi flow saat ini tidak pernah mengatur status menjadi `Checked In`; setelah check-in status menjadi `Awaiting Approval`, lalu `Approved`.

## Checklist Operasional

Setelah install app:

1. Pastikan role `Visitor Manager`, `Visitor Security`, dan `Employee` tersedia.
2. Pastikan data Employee punya `user_id`, `status = Active`, dan department.
3. Buat Visitor baru.
4. Cek apakah QR code berhasil muncul di field `qr_code_image`.
5. Buka halaman `visitor-scanner`.
6. Scan QR atau masukkan Visitor ID manual.
7. Jalankan check-in.
8. Login sebagai host/employee atau manager untuk approve/reject.
9. Jalankan `end_visit` saat kunjungan selesai.
10. Jalankan checkout dari scanner.
11. Cek record `Visitor Log` untuk audit trail.

## Perintah Berguna

```bash
bench --site nama_site migrate
bench --site nama_site clear-cache
bench --site nama_site clear-website-cache
bench build
bench restart
bench --site nama_site list-apps
bench --site nama_site console
```

Memanggil API dari browser/session Frappe:

```javascript
frappe.call({
  method: "visitor_management.visitor_management.api.get_dashboard_data",
  callback: function (r) {
    console.log(r.message);
  }
});
```

Contoh QR data:

```json
{
  "visitor_id": "VIS-2026-05-00001",
  "visitor_name": "Nama Tamu",
  "host": "HR-EMP-00001"
}
```
