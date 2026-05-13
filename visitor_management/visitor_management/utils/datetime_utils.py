from frappe.utils import now_datetime, add_hours


def now():
    return now_datetime()


def hours_ago(hours):
    return add_hours(now_datetime(), -abs(hours))
