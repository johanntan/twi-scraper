"""Print one version's section of CHANGELOG.md, for the GitHub release notes.

Usage: python3 .github/changelog_notes.py 0.2.0

Fails if CHANGELOG.md has no `## [0.2.0]` section, or the section is empty, so a
version can't be released without its changelog entry.
"""

import re
import sys
from pathlib import Path

version = sys.argv[1]
text = Path(__file__).resolve().parent.parent.joinpath("CHANGELOG.md").read_text()
match = re.search(
    rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S
)
notes = match.group(1).strip() if match else ""
if not notes:
    sys.exit(f"CHANGELOG.md has no entry for {version}. Add a '## [{version}]' section.")
print(notes)
