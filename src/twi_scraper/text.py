"""Normalize chapter text for readable and screen-reader-friendly output."""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag

REDACTION_LABEL = "Redacted in original"
LITERAL_REDACTION = "[redacted]"
_REDACTION_CLASS_PATTERN = re.compile(
	r"(?:^|[-_])(spoiler|redact(?:ed|ion)?|blackout|censor(?:ed)?)(?:$|[-_])",
	re.IGNORECASE,
)
_MARKDOWN_HTML_REDACTION_PATTERN = re.compile(
	r"<(?P<tag>span|font|mark)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
	re.IGNORECASE | re.DOTALL,
)


def normalize_accessible_text(value: str) -> str:
	return unicodedata.normalize("NFKC", value)


def normalize_accessible_markdown(markdown: str) -> str:
	protected: list[str] = []

	def protect(match: re.Match[str]) -> str:
		protected.append(match.group(0))
		return f"\x00TWI-PROTECTED-{len(protected) - 1}\x00"

	def protect_markdown_link(match: re.Match[str]) -> str:
		label = normalize_accessible_text(match.group("label"))
		label = re.sub(r"█+", r"\[redacted\]", label)
		protected.append(f"{match.group('prefix')}[{label}]({match.group('destination')})")
		return f"\x00TWI-PROTECTED-{len(protected) - 1}\x00"

	value = re.sub(r"(?ms)^(```|~~~).*?^\1[ \t]*$", protect, markdown)
	value = re.sub(r"(?<!`)`[^`\n]+`(?!`)", protect, value)
	value = _reveal_markdown_html_redactions(value)
	value = re.sub(
		r"(?P<prefix>!?)\[(?P<label>[^\]\n]*)\]\((?P<destination>[^)\n]+)\)",
		protect_markdown_link,
		value,
	)
	value = re.sub(r"(?i)\b(?:href|src)\s*=\s*([\"']).*?\1", protect, value)
	value = re.sub(r"(?<=\]\()[^)\n]+(?=\))", protect, value)
	value = re.sub(r"https?://[^\s<]+", protect, value)
	value = normalize_accessible_text(value)
	value = re.sub(r"█+", LITERAL_REDACTION, value)

	for index, original in enumerate(protected):
		value = value.replace(f"\x00TWI-PROTECTED-{index}\x00", original)
	return value


def normalize_accessible_html(html: str) -> str:
	soup = BeautifulSoup(html, "lxml")
	root = soup.body or soup
	normalize_tag_redactions(root)
	_normalize_text_nodes(root)

	if soup.body is None:
		return str(soup)
	return "".join(str(child) for child in soup.body.children)


def normalize_tag_text(root: Tag) -> None:
	_normalize_text_nodes(root)


def normalize_tag_redactions(root: Tag) -> None:
	candidates = [
		node
		for node in root.find_all(True)
		if _is_text_redaction_candidate(node)
		and _is_css_redaction(node)
		and not _has_redacted_ancestor(node, root)
	]
	for node in candidates:
		_reveal_css_redaction(node)

	for text_node in list(root.find_all(string=True)):
		if not isinstance(text_node, NavigableString) or _inside_preformatted_text(text_node):
			continue
		value = re.sub(r"█+", LITERAL_REDACTION, str(text_node))
		if value != str(text_node):
			text_node.replace_with(value)


def _normalize_text_nodes(root: Tag) -> None:
	for node in list(root.find_all(string=True)):
		if not isinstance(node, NavigableString):
			continue
		normalized = normalize_accessible_text(str(node))
		if normalized != str(node):
			node.replace_with(normalized)


def _reveal_markdown_html_redactions(markdown: str) -> str:
	def reveal(match: re.Match[str]) -> str:
		soup = BeautifulSoup(match.group(0), "lxml")
		node = soup.find(match.group("tag"))
		if not isinstance(node, Tag) or not _is_css_redaction(node):
			return match.group(0)
		return f"[{REDACTION_LABEL}: {match.group('body')}]"

	value = markdown
	while True:
		updated = _MARKDOWN_HTML_REDACTION_PATTERN.sub(reveal, value)
		if updated == value:
			return value
		value = updated


def _is_css_redaction(node: Tag) -> bool:
	classes = node.get("class", [])
	if isinstance(classes, str):
		classes = classes.split()
	if any(_REDACTION_CLASS_PATTERN.search(str(class_name)) for class_name in classes):
		return True

	declarations = _parse_style(str(node.get("style") or ""))
	color = _canonical_color(
		declarations.get("-webkit-text-fill-color") or declarations.get("color")
	)
	background = _canonical_color(
		declarations.get("background-color") or declarations.get("background")
	)
	return any(
		(
			color == "transparent",
			_is_zero_css_value(declarations.get("opacity")),
			declarations.get("visibility", "").strip().lower() in {"hidden", "collapse"},
			declarations.get("display", "").strip().lower() == "none",
			_is_zero_css_value(declarations.get("font-size")),
			_has_nonzero_blur(declarations.get("filter")),
			color is not None and background is not None and color == background,
		)
	)


def _reveal_css_redaction(node: Tag) -> None:
	declarations = _parse_style(str(node.get("style") or ""))
	matching_colors = _colors_match(declarations)
	text_fill = _canonical_color(declarations.get("-webkit-text-fill-color"))
	color = _canonical_color(declarations.get("color"))
	if text_fill == "transparent":
		declarations.pop("-webkit-text-fill-color", None)
	if color == "transparent":
		declarations.pop("color", None)
	if matching_colors:
		declarations.pop("color", None)
		declarations.pop("-webkit-text-fill-color", None)
		declarations.pop("background", None)
		declarations.pop("background-color", None)
	if _is_zero_css_value(declarations.get("opacity")):
		declarations.pop("opacity", None)
	if declarations.get("visibility", "").strip().lower() in {"hidden", "collapse"}:
		declarations.pop("visibility", None)
	if declarations.get("display", "").strip().lower() == "none":
		declarations.pop("display", None)
	if _is_zero_css_value(declarations.get("font-size")):
		declarations.pop("font-size", None)
	if _has_nonzero_blur(declarations.get("filter")):
		declarations.pop("filter", None)

	if declarations:
		node["style"] = "; ".join(f"{name}: {value}" for name, value in declarations.items())
	else:
		node.attrs.pop("style", None)

	classes = node.get("class", [])
	if isinstance(classes, str):
		classes = classes.split()
	kept_classes = [
		class_name for class_name in classes if not _REDACTION_CLASS_PATTERN.search(str(class_name))
	]
	if kept_classes:
		node["class"] = kept_classes
	else:
		node.attrs.pop("class", None)

	node.insert(0, NavigableString(f"[{REDACTION_LABEL}: "))
	node.append(NavigableString("]"))


def _parse_style(style: str) -> dict[str, str]:
	declarations: dict[str, str] = {}
	for declaration in style.split(";"):
		if ":" not in declaration:
			continue
		name, value = declaration.split(":", 1)
		name = name.strip().lower()
		value = value.strip()
		if name and value:
			declarations[name] = value
	return declarations


def _canonical_color(value: str | None) -> str | None:
	if value is None:
		return None
	color = re.sub(r"\s+", "", value).lower().replace("!important", "")
	match = re.search(r"(transparent|#[0-9a-f]{3,8}|rgba?\([^)]+\)|\bwhite\b|\bblack\b)", color)
	if match:
		color = match.group(1)
	aliases = {
		"white": "#ffffff",
		"#fff": "#ffffff",
		"black": "#000000",
		"#000": "#000000",
	}
	if color in aliases:
		return aliases[color]
	if re.fullmatch(r"#[0-9a-f]{4}", color) and color[-1] == "0":
		return "transparent"
	if re.fullmatch(r"#[0-9a-f]{8}", color) and color[-2:] == "00":
		return "transparent"
	if re.fullmatch(r"#[0-9a-f]{6}", color):
		return color
	rgba = re.fullmatch(r"rgba\((\d+),(\d+),(\d+),([^)]+)\)", color)
	if rgba and _is_zero_css_value(rgba.group(4)):
		return "transparent"
	rgb = re.fullmatch(r"rgba?\((\d+),(\d+),(\d+)(?:,[^)]+)?\)", color)
	if rgb:
		return "#" + "".join(f"{int(part):02x}" for part in rgb.groups())
	return color


def _is_zero_css_value(value: str | None) -> bool:
	if value is None:
		return False
	normalized = value.strip().lower().replace("!important", "")
	return bool(re.fullmatch(r"(?:0+(?:\.0+)?|\.0+)(?:px|em|rem|%)?", normalized))


def _has_nonzero_blur(value: str | None) -> bool:
	if value is None:
		return False
	match = re.search(r"\bblur\(([^)]+)\)", value, re.IGNORECASE)
	return match is not None and not _is_zero_css_value(match.group(1))


def _colors_match(declarations: dict[str, str]) -> bool:
	color = _canonical_color(
		declarations.get("-webkit-text-fill-color") or declarations.get("color")
	)
	background = _canonical_color(
		declarations.get("background-color") or declarations.get("background")
	)
	return color is not None and background is not None and color == background


def _has_redacted_ancestor(node: Tag, root: Tag) -> bool:
	parent = node.parent
	while isinstance(parent, Tag) and parent is not root:
		if _is_css_redaction(parent):
			return True
		parent = parent.parent
	return False


def _is_text_redaction_candidate(node: Tag) -> bool:
	if node.name in {"code", "pre", "script", "style", "noscript"}:
		return False
	return bool(node.get_text(" ", strip=True))


def _inside_preformatted_text(node: NavigableString) -> bool:
	return any(parent.name in {"code", "pre"} for parent in node.parents if isinstance(parent, Tag))
