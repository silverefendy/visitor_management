# Copyright (c) 2026, FnD Corp and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today

EXTRA_TEST_RECORD_DEPENDENCIES = ["Company", "Employee", "Visitor"]
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestVisitorLog(IntegrationTestCase):
    """Integration tests for Visitor Log."""

    def setUp(self):
        super().setUp()
        self.company = self._ensure_company()
        self.employee = self._make_employee()
        self.visitor = self._make_visitor()

    def tearDown(self):
        frappe.db.rollback()
        super().tearDown()

    def _ensure_company(self):
        company = frappe.db.get_value("Company", {}, "name")
        if company:
            return company

        doc = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": "VMS Test Company",
                "abbr": "VTC",
                "default_currency": "USD",
                "country": "Indonesia",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_employee(self):
        employee_name = "VMS Log Host {0}".format(frappe.generate_hash(length=6))
        doc = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "VMS",
                "last_name": "LogHost",
                "employee_name": employee_name,
                "company": self.company,
                "status": "Active",
                "date_of_joining": today(),
                "gender": "Male",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_visitor(self):
        doc = frappe.get_doc(
            {
                "doctype": "Visitor",
                "visitor_name": "Log Test Visitor",
                "visitor_phone": "0800000000",
                "id_type": "KTP",
                "id_number": "LOG-{0}".format(frappe.generate_hash(length=8)),
                "visit_purpose": "Visitor log test",
                "host_employee": self.employee,
            }
        )
        return doc.insert(ignore_permissions=True)

    def test_log_auto_fills_action_time(self):
        before = now_datetime()
        log = frappe.get_doc(
            {
                "doctype": "Visitor Log",
                "visitor": self.visitor.name,
                "action": "Check In",
            }
        ).insert(ignore_permissions=True)
        after = now_datetime()

        self.assertTrue(log.action_time)
        self.assertGreaterEqual(log.action_time, before)
        self.assertLessEqual(log.action_time, after)

    def test_log_auto_fills_action_by(self):
        log = frappe.get_doc(
            {
                "doctype": "Visitor Log",
                "visitor": self.visitor.name,
                "action": "Check In",
                "action_time": now_datetime(),
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(log.action_by, frappe.session.user)
