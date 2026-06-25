#!/usr/bin/env python3
"""Generate an X post draft from the next queued theme using the Claude API.

Reads a style guide and example posts from the repo, picks a theme from
themes.txt (rotating by date, so it needs no write-back), asks Claude to draft
a post in that voice, and writes the issue title/body that the approval
workflow turns into a review issue.

Style source preference (first that exists wins):
  - x-manager/reference/x-style-profile.md   (learned via fetch_style.py)
  - x-manager/reference/x-writing-guidelines.md  (the plugin's default)
and likewise x-style-examples.md -> x-writing-examples.md.

The generated post text is wrapped between HTML-comment markers so the
publish step can extract it reliably from the issue body.
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REF = REPO / "x-manager" / "reference"
OUT = Path(os.environ.get("OUT_DIR", HERE / ".out"))

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MARK_START = "<!--POST_START-->"
MARK_END = "<!--POST_END-->"


def read_first(paths):
    for path in paths:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def pick_theme():
    """Pick a theme by rotating through themes.txt based on the current day."""
    raw = (HERE / "themes.txt").read_text(encoding="utf-8")
    themes = [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not themes:
        return None
    idx = int(time.time() // 86400) % len(themes)
    return themes[idx]


def main():
    theme = pick_theme()
    if not theme:
        print("themes.txt is empty — nothing to generate.", file=sys.stderr)
        return 0  # not an error; the workflow simply opens no issue

    style_guide = read_first([REF / "x-style-profile.md", REF / "x-writing-guidelines.md"])
    examples = read_first([REF / "x-style-examples.md", REF / "x-writing-examples.md"])
    if not style_guide:
        print("No style guide found in x-manager/reference/.", file=sys.stderr)
        return 1
    profile = os.environ.get("ACCOUNT_PROFILE", "(no extra account context provided)")

    system = f"""You are an expert X (Twitter) ghostwriter. Study the STYLE GUIDE and \
EXAMPLE POSTS below, then write ONE original X post on the given theme.

Rules:
- Match the language, voice, tone, structure, length, and formatting conventions \
shown in the style guide and examples.
- Write original content — do not copy phrases verbatim from the examples.
- Output ONLY the post text. No headings, no preamble, no explanations, no \
surrounding quotes.

# STYLE GUIDE
{style_guide}

# EXAMPLE POSTS
{examples}
"""
    user = f"""Theme: {theme}

Account context:
{profile}

Write one X post on this theme, following the style guide. Output the post text only."""

    try:
        from anthropic import Anthropic
    except ImportError:
        print("The 'anthropic' package is not installed.", file=sys.stderr)
        return 1

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    post = "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    ).strip()
    if not post:
        print("Claude returned an empty post.", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    body = (
        "🤖 Auto-generated draft. Review it, and if it looks good add the "
        "**`x-approve`** label to publish it. To skip, just close this issue.\n\n"
        f"**Theme:** {theme}\n"
        f"**Characters:** {len(post)} (posts over 280 require X Premium)\n\n"
        "---\n\n"
        f"{MARK_START}\n{post}\n{MARK_END}\n"
    )
    (OUT / "body.md").write_text(body, encoding="utf-8")
    (OUT / "title.txt").write_text(f"[X draft] {theme}", encoding="utf-8")
    print(f"Generated draft for theme: {theme} ({len(post)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
