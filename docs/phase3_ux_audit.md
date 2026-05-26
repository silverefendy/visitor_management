# Phase 3 UX & Operational Audit (Frappe v16 Visitor Management)

## 1) UX Audit Report

### Current strengths
- Web scanner page already combines camera scan, manual fallback, and dashboard summary in one route (`/vms-scanner`).
- Security operators can execute check-in/check-out with minimal steps.
- Active/pending/rejected sections provide quick operational context.

### Current gaps
- Scanner feedback is text-only and transient; no persistent “recent scans” list.
- Navigation grouping is unclear across visitor, approval, scanner, and gate operations.
- Mobile ergonomics are acceptable but not optimized for long-running gate workflows.
- Operational pages are mixed (scanner + dashboard) and can cause cognitive overload.

## 2) Operational Friction Analysis

1. **Scan confidence friction**
   - Operators do not get strong persistent feedback after each scan (history trail missing).
2. **Context switching friction**
   - Approval and active-visitor monitoring live across different surfaces with inconsistent entry points.
3. **Error resolution friction**
   - Scanner errors are shown, but follow-up action guidance is limited.
4. **Shift handover friction**
   - No explicit “recent gate activity” timeline optimized for shift change checks.

## 3) Recommended Menu Structure (non-breaking)

Use existing routes/doctype pages but regroup labels:

### A. Operations
- Security Scanner (`/vms-scanner`)
- Active Visitors (report/page)
- Recent Activity (report/page)

### B. Visitor Management
- Visitors (DocType list)
- Pending Approvals
- Completed Visits
- Rejected Visitors

### C. Employee Access
- Employee Entry Requests
- Employee Entry Logs

### D. Security & Gates
- Gates
- Gate Device Mapping / Gate Activity

### E. Analytics & Reports
- Daily Visitor Metrics
- Approval SLA
- Visit Duration Trends

### F. Administration
- Settings / Workflow Rules
- Notification Templates
- Role & Permission Audit

## 4) Mobile Usability Findings

- Button sizes are generally usable; mode/target buttons should keep minimum 44px touch target.
- Scanner card should prioritize camera viewport first on sub-768px screens.
- Action buttons should stay sticky/visible after scan result on tablets.
- Dashboard tables should support compact card fallback on small screens.

## 5) Scanner Modernization Recommendations (API-compatible)

1. Add persistent recent scan list (last 5–10 events).
2. Add optional sound cues (success/failure).
3. Improve loading states:
   - "Validating QR..."
   - "Processing check-in/check-out..."
4. Keep current `scan_qr_action` and `get_visitor_by_qr` contracts.
5. Standardize user-facing errors with short operator guidance.

## 6) Incremental Implementation Plan

### Sprint P3.1 (Low risk)
- Add scanner feedback module (recent scans + optional sound toggle).
- Add clearer status badges and loading labels.
- Keep backend unchanged.

### Sprint P3.2 (Low-medium risk)
- Introduce Active Visitors dedicated operational view.
- Add Pending Approvals quick board with fast actions.
- Reuse existing API/dashboard endpoints.

### Sprint P3.3 (Medium risk)
- Reorganize workspace/menu labels into operational groups.
- Add Analytics lightweight cards (today/active/pending/rejected).

### Sprint P3.4 (Medium risk)
- Mobile/tablet polish: sticky action row, compact tables, scan ergonomics.
- Print badge layout refresh (QR prominence + host clarity + validity block).

## Guardrails
- Preserve current QR lifecycle and visitor status transitions.
- Preserve scanner API response compatibility.
- Prefer additive UI changes over structural rewrites.
