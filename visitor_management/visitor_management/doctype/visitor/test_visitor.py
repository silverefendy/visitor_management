# Copyright (c) 2026, FnD Corp and Contributors
# See license.txt

import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from visitor_management.visitor_management.services.visitor_service import (
    check_in,
    validate_duplicate_active,
)

EXTRA_TEST_RECORD_DEPENDENCIES = ["Company", "Employee"]
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestVisitor(IntegrationTestCase):
    """Integration tests for Visitor."""

    def setUp(self):
        super().setUp()
        self.company = self._ensure_company()
        self.employee = self._make_employee()

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
        employee_name = "VMS Test Host {0}".format(frappe.generate_hash(length=6))
        doc = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": "VMS",
                "last_name": "Host",
                "employee_name": employee_name,
                "company": self.company,
                "status": "Active",
                "date_of_joining": today(),
                "gender": "Male",
            }
        )
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_visitor(self, id_number, **kwargs):
        data = {
            "doctype": "Visitor",
            "visitor_name": "Test Visitor",
            "visitor_phone": "0800000000",
            "id_type": "KTP",
            "id_number": id_number,
            "visit_purpose": "Integration test",
            "host_employee": self.employee,
        }
        data.update(kwargs)
        return frappe.get_doc(data).insert(ignore_permissions=True)

    def test_visitor_naming(self):
        visitor = self._make_visitor("NAME-{0}".format(frappe.generate_hash(length=6)))
        pattern = re.compile(r"^VIS-\d{4}-\d{2}-\d{5}$")
        self.assertRegex(visitor.name, pattern)

    def test_status_default_on_insert(self):
        visitor = self._make_visitor("STAT-{0}".format(frappe.generate_hash(length=6)))
        self.assertEqual(visitor.status, "Registered")

    def test_duplicate_active_visitor_rejected(self):
        id_number = "DUP-{0}".format(frappe.generate_hash(length=8))
        first = frappe.get_doc("Visitor", self._make_visitor(id_number).name)
        check_in(first)

        duplicate = frappe.get_doc(
            {
                "doctype": "Visitor",
                "visitor_name": "Duplicate Visitor",
                "visitor_phone": "0800000001",
                "id_type": "KTP",
                "id_number": id_number,
                "visit_purpose": "Duplicate test",
                "host_employee": self.employee,
            }
        )

        with self.assertRaises(frappe.ValidationError):
            validate_duplicate_active(duplicate)

        with self.assertRaises(frappe.ValidationError):
            duplicate.insert(ignore_permissions=True)

    def test_checkin_changes_status(self):
        visitor = frappe.get_doc(
            "Visitor",
            self._make_visitor("CHK-{0}".format(frappe.generate_hash(length=6))).name,
        )
        self.assertEqual(visitor.status, "Registered")

        check_in(visitor)
        visitor.reload()

        self.assertEqual(visitor.status, "Awaiting Approval")
        self.assertTrue(visitor.check_in_time)
