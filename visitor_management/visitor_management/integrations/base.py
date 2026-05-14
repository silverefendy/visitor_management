class AccessDeviceAdapter:
	"""Contract for future access device drivers."""

	def ping(self):
		raise NotImplementedError

	def push_event(self, payload):
		raise NotImplementedError
