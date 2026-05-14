from frappe.utils import now_datetime, add_to_date


def now():
    return now_datetime()


def hours_ago(hours):
    return add_to_date(now_datetime(), hours=-abs(hours))
