"""EXAMPLE.md's index and its internal links stay in step with its headings.

The index is written by hand. Nothing else in the repo notices when a section is
added, renamed or removed, so it would rot silently -- and a wrong index is
worse than none, because it looks authoritative. These two tests are the check.

Slug generation is not as obvious as it looks: a `#` inside a fenced code block
is not a heading (EXAMPLE.md has a literal `# 0.75` in a Python snippet), and
GitHub keeps underscores while dropping backticks, commas, colons and em-dashes.
"""
import re

from conftest import REPO_ROOT

DOC = REPO_ROOT / "EXAMPLE.md"
INDEX_HEADING = "Contents"


def slug(title):
    """GitHub's heading slug: lowercase, keep [a-z0-9_-] and spaces, spaces -> '-'."""
    return re.sub(r"[^a-z0-9_\- ]", "", title.lower()).replace(" ", "-")


def headings(text, levels=(2, 3)):
    """Every `##`/`###` heading, skipping fenced code blocks."""
    fence, found = False, []
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        match = re.match(r"^(#{1,6}) (.+)$", line)
        if match and len(match.group(1)) in levels:
            found.append(match.group(2))
    return found


def test_every_section_is_in_the_index():
    text = DOC.read_text(encoding="utf-8")
    titles = [t for t in headings(text) if t != INDEX_HEADING]
    index = "\n".join(re.findall(r"^\s*- \[.+\]\(#.+\)$", text, flags=re.M))
    missing = [t for t in titles if f"[{t}](#{slug(t)})" not in index]
    assert not missing, f"EXAMPLE.md sections absent from its index: {missing}"


def test_every_internal_link_resolves():
    text = DOC.read_text(encoding="utf-8")
    # Anchors of headings at every level, not just the two the index lists.
    anchors = {slug(t) for t in headings(text, levels=range(1, 7))}
    # Bare '#...' targets only -- a './README.md#choosing-d' is another file's.
    targets = re.findall(r"\]\(#([^)]+)\)", text)
    dangling = sorted({t for t in targets if t not in anchors})
    assert not dangling, f"EXAMPLE.md links to anchors that do not exist: {dangling}"
