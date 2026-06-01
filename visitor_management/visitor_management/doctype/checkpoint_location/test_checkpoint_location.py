import frappe
from frappe.tests.utils import FrappeTestCase


class TestCheckpointLocation(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_checkpoint_creation(self):
        checkpoint = frappe.get_doc({
            "doctype": "Checkpoint Location",
            "checkpoint_id": "TEST-GATE-001",
            "checkpoint_name": "Test Gate 1",
            "description": "Test checkpoint for validation",
            "active": 1
        })
        checkpoint.insert()
        self.assertEqual(checkpoint.checkpoint_id, "TEST-GATE-001")
        self.assertTrue(checkpoint.active)

    def test_duplicate_checkpoint_id(self):
        frappe.get_doc({
            "doctype": "Checkpoint Location",
            "checkpoint_id": "DUP-TEST",
            "checkpoint_name": "Duplicate Test",
            "active": 1
        }).insert()

        with self.assertRaises(frappe.DuplicateEntryError):
            frappe.get_doc({
                "doctype": "Checkpoint Location",
                "checkpoint_id": "DUP-TEST",
                "checkpoint_name": "Another Duplicate",
                "active": 1
            }).insert()

    def test_qr_payload_generation(self):
        checkpoint = frappe.get_doc({
            "doctype": "Checkpoint Location",
            "checkpoint_id": "QR-TEST",
            "checkpoint_name": "QR Test Gate",
            "active": 1
        })
        checkpoint.insert()
        
        payload = checkpoint.get_qr_payload()
        self.assertEqual(payload["checkpoint_id"], "QR-TEST")
        self.assertEqual(payload["checkpoint_name"], "QR Test Gate")

    def test_inactive_checkpoint_no_payload(self):
        checkpoint = frappe.get_doc({
            "doctype": "Checkpoint Location",
            "checkpoint_id": "INACTIVE-TEST",
            "checkpoint_name": "Inactive Gate",
            "active": 0
        })
        checkpoint.insert()
        
        payload = checkpoint.get_qr_payload()
        self.assertIsNone(payload)