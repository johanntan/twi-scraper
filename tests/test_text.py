from twi_scraper.text import normalize_accessible_html, normalize_accessible_markdown


def test_normalize_accessible_html_reveals_css_redactions_and_literal_blocks():
	html = """
	<div>
	  <p><span style="color: transparent">Transparent secret</span></p>
	  <p><span style="-webkit-text-fill-color: transparent">Text-fill secret</span></p>
	  <p><span style="color: rgba(0, 0, 0, 0)">Alpha secret</span></p>
	  <p><span style="opacity: 0; font-weight: bold">Opacity secret</span></p>
	  <p><span style="visibility: hidden">Visibility secret</span></p>
	  <p><span style="display: none">Display secret</span></p>
	  <p><span style="font-size: 0">Tiny secret</span></p>
	  <p><span style="filter: blur(4px)">Blurred secret</span></p>
	  <p><span style="color: #fff; background-color: white">White secret</span></p>
	  <p><span class="story-spoiler emphasis" style="color: red">Class secret</span></p>
	  <p><span style="color: #ff0000">Ordinary red text</span></p>
	  <p>There were ███ raiders.</p>
	  <pre>Keep ███ in preformatted text.</pre>
	  <code>Keep ██ in code.</code>
	  <a href="https://example.com/███">Link</a>
	</div>
	"""

	normalized = normalize_accessible_html(html)

	for secret in (
		"Transparent secret",
		"Text-fill secret",
		"Alpha secret",
		"Opacity secret",
		"Visibility secret",
		"Display secret",
		"Tiny secret",
		"Blurred secret",
		"White secret",
		"Class secret",
	):
		assert f"[Redacted in original: {secret}]" in normalized
	assert 'style="font-weight: bold"' in normalized
	assert 'class="emphasis"' in normalized
	assert 'style="color: red"' in normalized
	assert '<span style="color: #ff0000">Ordinary red text</span>' in normalized
	assert "There were [redacted] raiders." in normalized
	assert "<pre>Keep ███ in preformatted text.</pre>" in normalized
	assert "<code>Keep ██ in code.</code>" in normalized
	assert 'href="https://example.com/███"' in normalized


def test_normalize_accessible_markdown_preserves_code_and_link_destinations():
	markdown = """
Visible ███ text.

`inline ███ code`

```text
fenced ███ code
<span style="opacity: 0">not content</span>
```

[Link ███](https://example.com/███)

<span style="opacity: 0">Recoverable secret</span>
"""

	normalized = normalize_accessible_markdown(markdown)

	assert "Visible [redacted] text." in normalized
	assert "`inline ███ code`" in normalized
	assert "fenced ███ code" in normalized
	assert '<span style="opacity: 0">not content</span>' in normalized
	assert r"[Link \[redacted\]](https://example.com/███)" in normalized
	assert "[Redacted in original: Recoverable secret]" in normalized
