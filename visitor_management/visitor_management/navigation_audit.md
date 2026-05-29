# Visitor Management Structural Navigation Audit

## Inventory

### Custom DocTypes

| Category | DocType | Purpose | Navigation Decision |
| --- | --- | --- | --- |
| Main Operations | `Visitor` | Visitor registration, QR identity, status, and operational record. | Keep as the single visitor list. List-view buttons provide Today, Checked In, Checked Out, Pending, and This Month filters instead of duplicate menu pages. |
| Main Operations | `Visitor Log` | Immutable-ish visitor access history for scan/approval events. | Keep as the single operational log menu. |
| Main Operations | `Employee Entry Request` | Employee access request workflow used by scanner/employee entry route. | Secondary operational DocType; not part of the simplified main VMS menu. |
| Logs / History | `Employee Entry Log` | Employee entry audit history. | Kept for administrators/managers; lower Awesome Bar priority. |
| Logs / Maintenance | `VMS Cleanup Log` | Audit trail for archive/delete maintenance actions. | Visible in workspace quick lists for managers/admins. |
| Configuration | `Visitor Settings` | General visitor behavior, display, QR generation toggle, and retention policy. | Functional Single settings DocType. |
| Configuration | `QR Settings` | QR generation, scanner, expiry, and duplicate/reuse controls. | Functional Single settings DocType. |
| Configuration | `Approval Settings` | Approval workflow policy and escalation controls. | Functional Single settings DocType. |
| Configuration | `Notification Settings` | Email, WhatsApp/SMS, browser, and sound notification toggles. | Functional Single settings DocType. |
| Configuration | `Gate` | Gate/scanner device configuration with gate type and allowed-role metadata. | Configuration-only menu. |

### Pages and Web Routes

| Route | File | Audience | Navigation Decision |
| --- | --- | --- | --- |
| `/vms-scanner` | `www/vms-scanner.html` / `www/vms-scanner.py` | Security / receptionist | Primary operational entry point. Check In and Check Out aliases route here instead of separate workspace menus. |
| `/vms-approval` | `www/vms-approval.html` / `www/vms-approval.py` | Approver / manager | Kept as an approval workbench, accessible by role and Awesome Bar/workflow use. |
| `/employee-entry` | `www/employee-entry.html` / `www/employee-entry.py` | Employees / HR | Secondary employee access flow. |
| `/app/vms-data-cleanup` | `page/vms_data_cleanup` | Manager / system admin | Dedicated maintenance page with preview, select, archive, delete confirmation, and cleanup audit logs. |
| `/app/visitor-scanner` | `page/visitor_scanner` | Desk users | Legacy Desk scanner page retained, but `/vms-scanner` is the preferred operations route. |

## Duplicate Menu Cleanup

The workspace main menu was reduced to six production operations:

1. Visitor
2. Scan QR
3. Visitor Logs
4. Reports
5. Settings
6. Data Cleanup

Removed as separate workspace menu concepts:

- `Check In` and `Check Out`: both are operational scan outcomes handled through `Scan QR`.
- `Today's Visitors`: now a built-in Visitor list filter, not a separate menu/page.
- Duplicate checked-in/checked-out/pending shortcuts: now list-view filters and Awesome Bar aliases.

## Role-Based Intent

- Security Guard: scan QR and view visitor status/logs only.
- Receptionist: create/edit visitors, scan QR, and view logs.
- Approver: approve/reject visitor requests and view pending approvals.
- Manager: reports, statistics, export, and cleanup preview/archive.
- VMS System Admin/System Manager: settings, data cleanup deletion, permissions, and full logs.

## Cleanup Safety

The Data Cleanup page requires privileged roles, supports preview before action, checkbox selection, archive instead of delete, a typed `DELETE` confirmation for destructive actions, and writes `VMS Cleanup Log` records for auditability.
