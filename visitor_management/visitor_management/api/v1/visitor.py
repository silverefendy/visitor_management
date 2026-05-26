"""v1 visitor dashboard and approval-list endpoints."""

from visitor_management.visitor_management import api as legacy_api

get_visitor_by_qr = legacy_api.get_visitor_by_qr
get_dashboard_data = legacy_api.get_dashboard_data
employee_pending_approvals = legacy_api.employee_pending_approvals
employee_approval_data = legacy_api.employee_approval_data
