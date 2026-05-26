import frappe


def success_response(message=None, **data):
    response = {"status": "success", "message": message}
    response.update(data)
    return response


def error_response(message, **data):
    response = {"status": "error", "message": message, "error": message}
    response.update(data)
    return response


def normalize_exception_message(err):
    message = getattr(err, "message", None)
    if isinstance(message, str) and message.strip():
        return message
    return str(err) if str(err).strip() else "Terjadi kesalahan"


def fail(message, exc=frappe.PermissionError):
    raise exc(message)
