class TwiEpubError(Exception):
	"""Base error for user-facing failures."""


class LockedChapterError(TwiEpubError):
	"""Raised when a chapter is present but gated from the current session."""


class ParseError(TwiEpubError):
	"""Raised when expected Wandering Inn page structure cannot be parsed."""
