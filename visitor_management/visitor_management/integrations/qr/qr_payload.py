import json


def parse_qr_payload(raw):
	"""Parse scanner/QR payload into a normalized dict without business rules."""
	if isinstance(raw, dict):
		return raw
	if not raw:
		return {}

	value = str(raw).strip()
	try:
		parsed = json.loads(value)
		return parsed if isinstance(parsed, dict) else {"value": parsed}
	except Exception:
		return {"value": value}
