# Visitor Management Structural Navigation Audit

## Final Workspace Structure

The workspace intentionally exposes only six high-level menus:

### Main Operations

1. `Visitor` — the single visitor list and form entry point. Today, Checked In, Checked Out, Pending, and This Month are list-view filters, not duplicate menu pages.
2. `Scan QR` — the primary operational scanner entry point for check-in/check-out flow.
3. `Visitor Logs` — access history and scan/approval audit trail.

### Reports

4. `Reports` — report view for Visitor data.

### Administration

5. `Settings` — opens Visitor Settings; other VMS setting doctypes are reachable by search/Awesome Bar and linked DocType navigation.
6. `Data Cleanup` — dedicated maintenance page for archive/delete operations.

Removed duplicate workspace menu concepts:

- Today Visitor / visitor duplicate pages.
- Separate Check In and Check Out pages; scanner resolves the correct action.
- Duplicate filtered report shortcuts.
- Cleanup Log as a visible operational quick list.

## Custom DocType Visibility

| Category | DocType | Purpose | Visibility Decision |
| --- | --- | --- | --- |
| Main Operations | `Visitor` | Visitor registration, QR identity, status, and operational record. | Workspace shortcut + quick list. |
| Main Operations | `Visitor Log` | Visitor access and workflow history. | Workspace shortcut + quick list. |
| Secondary Operations | `Employee Entry Request` | Employee access request workflow used by scanner/employee entry route. | Search/DocType access only; not in main workspace. |
| History | `Employee Entry Log` | Employee entry audit history. | Admin/report access only; not in main workspace. |
| Audit/Internal | `VMS Cleanup Log` | System-generated cleanup audit history. | Not manually creatable/editable; visible from cleanup page history and report/search for admins only. |
| Configuration | `Visitor Settings` | General visitor behavior, display, QR generation toggle, and retention policy. | Functional Single settings DocType. |
| Configuration | `QR Settings` | QR generation, scanner, expiry, and duplicate/reuse controls. | Functional Single settings DocType. |
| Configuration | `Approval Settings` | Approval workflow policy and escalation controls. | Functional Single settings DocType. |
| Configuration | `VMS Notification Settings` | VMS-owned notification toggles; does not customize Frappe core Notification Settings. | Functional Single settings DocType. |
| Configuration | `Gate` | Gate/scanner device settings. | Configuration/search access; not in main operation menus. |

## Cleanup Tool Design

`VMS Cleanup Log` is no longer an operational UI. It is a system-generated audit trail only:

- no manual create permission;
- no manual write/delete permission;
- no import/create menu behavior;
- records are inserted only by `visitor_management.visitor_management.maintenance.run_cleanup`;
- human-readable filter fields replace raw JSON payload display.

The Data Cleanup page provides the enterprise workflow:

1. Select target DocType (`Visitor` or `Visitor Log`).
2. Apply filters (date range, older-than days, status, gate, company, visitor type, checked-out only).
3. Preview affected records.
4. Select rows or run filtered deletion.
5. Archive Visitor records or delete selected/filtered records.
6. Review cleanup history in a readable table.

## Pages and Routes

| Route | File | Decision |
| --- | --- | --- |
| `/vms-scanner` | `www/vms-scanner.html` / `www/vms-scanner.py` | Primary scanner operation route. |
| `/vms-approval` | `www/vms-approval.html` / `www/vms-approval.py` | Approval workbench route. |
| `/employee-entry` | `www/employee-entry.html` / `www/employee-entry.py` | Secondary employee access route. |
| `/app/vms-data-cleanup` | `page/vms_data_cleanup` | Dedicated cleanup tool. |
| `/app/visitor-scanner` | `page/visitor_scanner` | Legacy desk scanner page retained but not highlighted in workspace. |
