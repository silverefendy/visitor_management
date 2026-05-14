import frappe
from frappe.tests.utils import FrappeTestCase


class TestVisitorSecurityFlows(FrappeTestCase):
	def test_duplicate_active_validation_constant(self):
		from visitor_management.visitor_management.services.visitor_service import ACTIVE_STATUSES

		self.assertIn("Awaiting Approval", ACTIVE_STATUSES)

	def test_gate_role_constant(self):
		from visitor_management.visitor_management.permissions.gate_permissions import GATE_ROLES

		self.assertIn("Security User", GATE_ROLES)
		self.assertIn("Visitor Security", GATE_ROLES)

	def test_manager_role_constant(self):
		from visitor_management.visitor_management.permissions.approval_permissions import MANAGER_ROLES

		self.assertTrue({"System Manager", "HR Manager"}.issubset(MANAGER_ROLES))
