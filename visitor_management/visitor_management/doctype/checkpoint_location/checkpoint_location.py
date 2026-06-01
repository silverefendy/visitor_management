# Copyright (c) 2026, FnD Corp
# License: MIT. See LICENSE

import json
import frappe
from frappe import _
from frappe.utils import cstr
from visitor_management.visitor_management.services.qr_service import generate_qr_image


class CheckpointLocation(frappe.Document):
    def validate(self):
        self.validate_checkpoint_id()
        self.validate_active_status()

    def validate_checkpoint_id(self):
        """Ensure checkpoint_id is uppercase and alphanumeric with optional hyphens"""
        if self.checkpoint_id:
            clean_id = cstr(self.checkpoint_id).strip().upper()
            if not clean_id.replace("-", "").replace("_", "").isalnum():
                frappe.throw(_("Checkpoint ID must be alphanumeric (hyphens/underscores allowed)"))
            self.checkpoint_id = clean_id

    def validate_active_status(self):
        """Prevent duplicate active checkpoints with same ID"""
        if self.active and not self.is_new():
            existing = frappe.db.exists(
                "Checkpoint Location",
                {"checkpoint_id": self.checkpoint_id, "name": ["!=", self.name], "active": 1}
            )
            if existing:
                frappe.throw(_("Another active checkpoint with ID '{0}' already exists").format(self.checkpoint_id))

    @frappe.whitelist()
    def generate_qr_code(self):
        """Generate QR code payload for this checkpoint"""
        if not self.checkpoint_id:
            frappe.throw(_("Checkpoint ID is required to generate QR"))

        payload = {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_name": self.checkpoint_name
        }

        qr_data = json.dumps(payload)
        qr_image = generate_qr_image(qr_data)

        if qr_image:
            self.db_set("qr_code_image", qr_image, update_modified=False)
            frappe.msgprint(_("QR Code generated successfully"), indicator="green")
            return {"qr_data": qr_data, "qr_image": qr_image}

        frappe.throw(_("Failed to generate QR code"))

    def get_qr_payload(self):
        """Return the QR payload dict for external use"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_name": self.checkpoint_name
        } if self.active else None