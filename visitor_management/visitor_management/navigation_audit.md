# Visitor Management Navigation Audit

## Inventory

### Custom DocTypes

| Category | DocType | Purpose | Workspace | Awesome Bar |
| --- | --- | --- | --- | --- |
| Main Operations | `Visitor` | Visitor registration, approval, QR, check-in, and check-out record. | Primary shortcut, quick list, KPI source | Prioritized with search fields and VMS shortcuts |
| Main Operations | `Employee Entry Request` | Employee access request workflow used by the VMS scanner and employee entry portal. | Operational quick list and report shortcut | Searchable, but secondary to Visitor |
| Logs / History | `Visitor Log` | Visitor access audit trail and IN/OUT history. | Primary log shortcut and quick list | Searchable for audit lookup |
| Logs / History | `Employee Entry Log` | Employee entry audit history. | Operational quick list/report area | Lower priority in global search |
| Configuration | `Gate` | Gate/device configuration for scanner locations. | Configuration section only | Hidden from global search priority |

### Pages and Web Routes

| Route | File | Audience | Navigation Decision |
| --- | --- | --- | --- |
| `/vms-scanner` | `www/vms-scanner.html` / `www/vms-scanner.py` | Security / receptionist | Primary Scan QR, Check In, and Check Out shortcuts |
| `/vms-approval` | `www/vms-approval.html` / `www/vms-approval.py` | Visitor Manager / host approval users | Main Operations shortcut |
| `/employee-entry` | `www/employee-entry.html` / `www/employee-entry.py` | Employees / HR | Secondary operational list/report path |
| `/app/visitor-scanner` | `page/visitor_scanner` | Desk scanner page | Kept available for roles, but `/vms-scanner` is preferred for operations |

### Reports, Dashboards, Print Formats, Child Tables

No standard Query Report, Script Report, Dashboard, Print Format, or child-table DocTypes were found in this app tree. Workspace report shortcuts therefore route to filtered DocType list/report views instead of non-existent report records.

## Visibility Decisions

### Show Prominently

- Visitor
- Visitor Log
- Scan QR / VMS Scanner
- Check In / Check Out scanner intents
- Today's Visitors and operational filtered Visitor lists
- Pending Approval / Approval panel

### Show as Secondary Operations

- Employee Entry Request
- Employee Entry Log
- Employee Visit Report view

### Show Only Under Configuration

- Gate
- Visitor Settings / QR Settings / Approval Settings / Notification Settings placeholders, grouped in the smaller Configuration section until dedicated settings DocTypes exist.

### Hide or De-prioritize for Normal Search

- Gate is configuration-only and not shown in global search priority.
- Employee Entry Log is audit/system history and not shown in global search priority.
- No child tables were found, so no child-table Awesome Bar cleanup was required.

## Role-Based Navigation Intent

- Receptionist / Visitor Security: workspace focuses on Visitor, Scan QR, Check In, Check Out, active/pending/today filters, and logs.
- Visitor Manager / System Manager: additionally sees configuration links and all operational/audit lists through role permissions.
- Employee: workspace remains accessible for employee-related access flows but operational VMS shortcuts are grouped first for clarity.
