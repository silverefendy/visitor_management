import frappe


def get_request_ip() -> str | None:
	"""
	Ambil IP address dari request yang sedang berjalan.
	Mendukung proxy/load balancer via X-Forwarded-For header.
	"""
	try:
		request = getattr(frappe.local, "request", None)
		if not request:
			return None

		# Prioritaskan X-Forwarded-For (proxy/nginx/reverse proxy)
		forwarded_for = request.headers.get("X-Forwarded-For")
		if forwarded_for:
			return forwarded_for.split(",")[0].strip()

		# X-Real-IP (nginx)
		real_ip = request.headers.get("X-Real-IP")
		if real_ip:
			return real_ip.strip()

		# Direct IP dari WSGI environ
		return request.environ.get("REMOTE_ADDR")
	except Exception:
		return None


def get_gate_by_ip(ip_address: str | None) -> str | None:
	"""
	Cari Gate berdasarkan ip_address dari request.
	Cocokkan ke field ip_address di doctype Gate (status Active).
	"""
	if not ip_address:
		return None
	return frappe.db.get_value(
		"Gate",
		{"ip_address": ip_address, "status": "Active"},
		"name",
	)


def get_gate_by_device(device_id: str | None = None, gate: str | None = None) -> str | None:
	"""
	Resolve gate name dengan urutan prioritas:
	  1. gate (eksplisit dari parameter) -- paling prioritas
	  2. device_id -- cocokkan ke field device_id di Gate
	  3. IP address dari request -- auto-detect

	Kembalikan None jika tidak ada gate yang cocok.
	"""
	# Prioritas 1: gate eksplisit
	if gate:
		return gate

	# Prioritas 2: device_id
	if device_id:
		found = frappe.db.get_value(
			"Gate",
			{"device_id": device_id, "status": "Active"},
			"name",
		)
		if found:
			return found

	# Prioritas 3: auto-detect dari IP address request
	request_ip = get_request_ip()
	return get_gate_by_ip(request_ip)


def resolve_gate_for_scan(gate: str | None = None, device_id: str | None = None) -> str | None:
	"""
	Shorthand untuk dipakai di scan endpoints.
	Auto-detect IP jika gate dan device_id tidak diberikan.
	"""
	return get_gate_by_device(device_id=device_id, gate=gate)
