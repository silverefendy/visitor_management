"""v1 approval endpoints (backed by existing APIs)."""

from visitor_management.visitor_management import api as legacy_api

approve_visitor = legacy_api.approve_visitor
reject_visitor = legacy_api.reject_visitor
complete_visit = legacy_api.complete_visit
