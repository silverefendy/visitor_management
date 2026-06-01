# Copyright (c) 2026, FnD Corp
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, cint


class EmployeeCheckpoint(frappe.Document):
    def before_insert(self):
        self.set_employee_name()
        self.set_checkpoint_name()
        self.validate_duplicate_scan()

    def set_employee_name(self):
        if self.employee and not self.employee_name:
            self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")

    def set_checkpoint_name(self):
        if self.checkpoint_id and not self.checkpoint_name:
            self.checkpoint_name = frappe.db.get_value("Checkpoint Location", self.checkpoint_id, "checkpoint_name")

    def validate_duplicate_scan(self):
        """Prevent duplicate scans from same employee+checkpoint within 30 seconds"""
        if not self.employee or not self.checkpoint_id:
            return

        # Check for existing scan within last 30 seconds
        existing = frappe.db.exists(
            "Employee Checkpoint",
            {
                "employee": self.employee,
                "checkpoint_id": self.checkpoint_id,
                "datetime": [">=", get_datetime(now_datetime()).replace(microsecond=0) - frappe.utils.date_diff("00:00:30")],
                "name": ["!=", self.name] if self.name else ["!=", ""]
            }
        )

        if existing:
            frappe.throw(
                _("Duplicate scan prevented: Employee {0} already scanned checkpoint {1} within last 30 seconds").format(
                    self.employee, self.checkpoint_id
                ),
                frappe.DuplicateEntryError
            )

    def on_submit(self):
        """Update employee's current location after successful scan"""
        self.update_current_location()

    def update_current_location(self):
        """Upsert Employee Current Location record"""
        current = frappe.db.get_value("Employee Current Location", {"employee": self.employee}, "name")
        
        location_data = {
            "employee": self.employee,
            "employee_name": self.employee_name,
            "last_checkpoint": self.checkpoint_id,
            "last_scan_time": self.datetime,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "device_id": self.device_id,
            "device_name": self.device_name
        }

        if current:
            frappe.db.set_value("Employee Current Location", current, location_data)
        else:
            frappe.get_doc({
                "doctype": "Employee Current Location",
                **location_data
            }).insert(ignore_permissions=True)

    @staticmethod
    def get_employee_recent_scans(employee, limit=10):
        """Get recent checkpoint scans for an employee"""
        return frappe.get_all(
            "Employee Checkpoint",
            filters={"employee": employee},
            fields=["name", "checkpoint_id", "checkpoint_name", "datetime", "latitude", "longitude", "device_id"],
            order_by="datetime desc",
            limit_page_length=limit
        )