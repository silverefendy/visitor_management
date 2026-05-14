import json


def parse_qr_payload(raw):
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
