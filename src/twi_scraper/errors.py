class TwiScraperError(Exception):
	"""Base error for user-facing failures."""


class LockedChapterError(TwiScraperError):
	"""Raised when a chapter is present but gated from the current session."""


class ParseError(TwiScraperError):
	"""Raised when expected Wandering Inn page structure cannot be parsed."""
