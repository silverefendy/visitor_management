import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_to_date


class TestEmployeeCurrentLocation(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_location_update(self):
        # Create initial location
        loc = frappe.get_doc({
            "doctype": "Employee Current Location",
            "employee": "EMP-TEST-LOC",
            "last_checkpoint": "TEST-CP-001",
            "last_scan_time": now_datetime(),
            "latitude": 3.5952,
            "longitude": 98.6722
        })
        loc.insert()
        
        # Update location
        loc.last_checkpoint = "TEST-CP-002"
        loc.last_scan_time = now_datetime()
        loc.save()
        
        # Verify update
        updated = frappe.db.get_value(
            "Employee Current Location",
            {"employee": "EMP-TEST-LOC"},
            "last_checkpoint"
        )
        self.assertEqual(updated, "TEST-CP-002")

    def test_stale_data_warning(self):
        # Create location with old timestamp
        old_time = add_to_date(now_datetime(), hours=-25)
        loc = frappe.get_doc({
            "doctype": "Employee Current Location",
            "employee": "EMP-STALE-TEST",
            "last_checkpoint": "TEST-CP-001",
            "last_scan_time": old_time
        })
        # Should trigger warning during validate
        loc.insert()