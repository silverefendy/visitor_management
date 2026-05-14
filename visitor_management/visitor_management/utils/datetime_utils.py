from frappe.utils import add_hours, now_datetime


def now():
	return now_datetime()


def hours_ago(hours):
	return add_hours(now_datetime(), -abs(hours))
