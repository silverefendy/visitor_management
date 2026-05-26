from frappe import _

from visitor_management.visitor_management.permissions.auth_helpers import ensure_roles

GATE_ROLES = {
    "System Manager",
    "Visitor Manager",
    "Visitor Security",
    "Security User",
}


def ensure_gate_access(user=None):
    ensure_roles(
        GATE_ROLES,
        user=user,
        message=_("Akses gate ditolak"),
    )
