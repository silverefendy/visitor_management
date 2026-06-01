# Copyright (c) 2026, FnD Corp
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, time_diff_in_seconds


class EmployeeCurrentLocation(frappe.Document):
    def before_insert(self):
        self.set_employee_name()

    def set_employee_name(self):
        if self.employee and not self.employee_name:
            self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")

    def validate(self):
        self.validate_scan_recency()

    def validate_scan_recency(self):
        """Warn if last scan is older than 24 hours (stale data)"""
        if self.last_scan_time:
            hours_old = time_diff_in_seconds(now_datetime(), self.last_scan_time) / 3600
            if hours_old > 24:
                frappe.msgprint(
                    _("Warning: Last scan for {0} was {1:.1f} hours ago").format(
                        self.employee_name, hours_old
                    ),
                    indicator="orange",
                    alert=True
                )

    @staticmethod
    def get_all_active_employees():
        """Get current locations for all employees with recent scans (< 24h)"""
        from frappe.utils import add_to_date
        cutoff = add_to_date(now_datetime(), hours=-24)
        
        return frappe.get_all(
            "Employee Current Location",
            filters={"last_scan_time": [">=", cutoff]},
            fields=[
                "employee", "employee_name", "last_checkpoint", 
                "last_scan_time", "latitude", "longitude", "device_name"
            ],
            order_by="last_scan_time desc"
        )

    @staticmethod
    def get_employee_location(employee):
        """Get current location for a specific employee"""
        return frappe.db.get_value(
            "Employee Current Location",
            {"employee": employee},
            ["last_checkpoint", "last_scan_time", "latitude", "longitude", "device_name"],
            as_dict=True
        )