from frappe.utils import add_to_date, now_datetime


def now():
    return now_datetime()


def hours_ago(hours):
    return add_to_date(now_datetime(), hours=-abs(hours))
