#!/usr/bin/env python3
"""Generate an X post draft from the next queued theme using the Claude API.

Reads the x-writing guidelines and examples committed in this repo, picks a
theme from themes.txt (rotating by date, so it needs no write-back), asks
Claude to draft a post, and writes the issue title/body that the approval
workflow turns into a review issue.

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

    guidelines = (REF / "x-writing-guidelines.md").read_text(encoding="utf-8")
    examples = (REF / "x-writing-examples.md").read_text(encoding="utf-8")
    profile = os.environ.get(
        "ACCOUNT_PROFILE",
        "(プロフィール未設定。一般的なビジネスパーソン向けのトーンで作成してください)",
    )

    system = f"""あなたは超優秀なX投稿文章作成のプロです。
以下のガイドラインと成功例に厳密に従って、X（Twitter）投稿文を1つ作成してください。
投稿文の本文だけを出力し、見出し・チェックリスト・補足説明・前置きは一切付けないこと。

# 文章要件・NGパターン（ガイドライン）
{guidelines}

# 成果がでた投稿例（トーン・構成・文量のお手本）
{examples}
"""
    user = f"""テーマ: {theme}

アカウント情報:
{profile}

上記テーマで、ガイドラインの7要素をすべて満たすX投稿文を1つ作成してください。
出力は投稿本文のみ。"""

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
        "🤖 自動生成された下書きです。内容を確認し、問題なければ "
        "`x-approve` ラベルを付けてください（付けると投稿されます）。\n"
        "スキップする場合はこの Issue を閉じてください。\n\n"
        f"**テーマ:** {theme}\n"
        f"**文字数:** {len(post)}（※280字超は X Premium が必要）\n\n"
        "---\n\n"
        f"{MARK_START}\n{post}\n{MARK_END}\n"
    )
    (OUT / "body.md").write_text(body, encoding="utf-8")
    (OUT / "title.txt").write_text(f"[X draft] {theme}", encoding="utf-8")
    print(f"Generated draft for theme: {theme} ({len(post)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
