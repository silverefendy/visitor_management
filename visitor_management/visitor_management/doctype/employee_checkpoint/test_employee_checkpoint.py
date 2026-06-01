import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_to_date


class TestEmployeeCheckpoint(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        # Create test checkpoint
        if not frappe.db.exists("Checkpoint Location", "TEST-CP-001"):
            frappe.get_doc({
                "doctype": "Checkpoint Location",
                "checkpoint_id": "TEST-CP-001",
                "checkpoint_name": "Test Checkpoint",
                "active": 1
            }).insert()

    def test_checkpoint_scan_creation(self):
        scan = frappe.get_doc({
            "doctype": "Employee Checkpoint",
            "employee": "EMP-001",
            "checkpoint_id": "TEST-CP-001",
            "datetime": now_datetime(),
            "latitude": 3.5952,
            "longitude": 98.6722,
            "device_id": "test-device-001",
            "source": "API"
        })
        scan.insert()
        self.assertEqual(scan.checkpoint_name, "Test Checkpoint")

    def test_duplicate_scan_prevention(self):
        # First scan
        scan1 = frappe.get_doc({
            "doctype": "Employee Checkpoint",
            "employee": "EMP-DUP-TEST",
            "checkpoint_id": "TEST-CP-001",
            "datetime": now_datetime(),
            "device_id": "test-device-dup"
        })
        scan1.insert()

        # Second scan within 30 seconds should fail
        with self.assertRaises(frappe.DuplicateEntryError):
            scan2 = frappe.get_doc({
                "doctype": "Employee Checkpoint",
                "employee": "EMP-DUP-TEST",
                "checkpoint_id": "TEST-CP-001",
                "datetime": now_datetime(),
                "device_id": "test-device-dup"
            })
            scan2.insert()

    def test_current_location_update(self):
        scan = frappe.get_doc({
            "doctype": "Employee Checkpoint",
            "employee": "EMP-LOC-TEST",
            "checkpoint_id": "TEST-CP-001",
            "datetime": now_datetime(),
            "latitude": 3.5952,
            "longitude": 98.6722,
            "device_id": "test-device-loc"
        })
        scan.insert()
        scan.submit()

        # Verify current location was updated
        current = frappe.db.get_value(
            "Employee Current Location",
            {"employee": "EMP-LOC-TEST"},
            ["last_checkpoint", "latitude", "longitude"],
            as_dict=True
        )
        self.assertEqual(current.last_checkpoint, "TEST-CP-001")
        self.assertEqual(current.latitude, 3.5952)