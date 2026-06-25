#!/usr/bin/env python3
"""Learn an X account's writing style and write it into the pipeline.

Fetches up to ~3,200 of a target account's most recent ORIGINAL tweets via the
X API v2 (App-only Bearer auth, read-only), then asks Claude to distill a
reusable style guide and pick representative examples. Outputs overwrite:

  x-manager/reference/x-style-profile.md    (the learned style guide)
  x-manager/reference/x-style-examples.md   (representative example posts)

generate.py prefers these files when present, so new drafts follow the learned
voice. Raw tweets are cached under x-manager/autopost/style/ (gitignored).

Note: the X user-timeline endpoint returns at most the ~3,200 most recent
tweets — not a full multi-year archive. That is an X API limit, not a bug.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REF = REPO / "x-manager" / "reference"
STYLE_DIR = HERE / "style"

API = "https://api.x.com/2"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
TARGET = os.environ.get("TARGET_USERNAME", "TheLongInvest").lstrip("@")
MAX_TWEETS = int(os.environ.get("MAX_TWEETS", "3200"))


def headers():
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        print("Missing X_BEARER_TOKEN (App-only Bearer token for read access).", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {token}"}


def api_get(url, params):
    for attempt in range(6):
        resp = requests.get(url, headers=headers(), params=params, timeout=30)
        if resp.status_code == 429:
            reset = int(resp.headers.get("x-rate-limit-reset", "0") or 0)
            wait = max(5, reset - int(time.time())) if reset else 15 * (attempt + 1)
            print(f"Rate limited; sleeping {min(wait, 900)}s", file=sys.stderr)
            time.sleep(min(wait, 900))
            continue
        if resp.status_code != 200:
            print(f"X API error {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)
        return resp.json()
    print("Giving up after repeated rate limits.", file=sys.stderr)
    sys.exit(1)


def resolve_user_id(username):
    data = api_get(f"{API}/users/by/username/{username}", {})
    uid = data.get("data", {}).get("id")
    if not uid:
        print(f"User @{username} not found.", file=sys.stderr)
        sys.exit(1)
    return uid


def fetch_tweets(uid):
    tweets = []
    params = {
        "max_results": 100,
        "exclude": "retweets,replies",
        "tweet.fields": "created_at,public_metrics,lang",
    }
    token = None
    while len(tweets) < MAX_TWEETS:
        if token:
            params["pagination_token"] = token
        data = api_get(f"{API}/users/{uid}/tweets", params)
        batch = data.get("data", [])
        if not batch:
            break
        tweets.extend(batch)
        token = data.get("meta", {}).get("next_token")
        if not token:
            break
    return tweets[:MAX_TWEETS]


def engagement(tweet):
    m = tweet.get("public_metrics", {})
    return m.get("like_count", 0) + 2 * m.get("retweet_count", 0)


def select_sample(tweets, limit=200, max_chars=60000):
    sample, total = [], 0
    for t in sorted(tweets, key=engagement, reverse=True):
        text = t.get("text", "").strip()
        if not text:
            continue
        sample.append(t)
        total += len(text)
        if len(sample) >= limit or total >= max_chars:
            break
    return sample


def distill(sample):
    from anthropic import Anthropic

    lines = []
    for t in sample:
        m = t.get("public_metrics", {})
        lines.append(f"[♥{m.get('like_count', 0)} ↻{m.get('retweet_count', 0)}] {t.get('text', '').strip()}")
    corpus = "\n\n---\n\n".join(lines)

    system = (
        "You are an expert ghostwriter analyzing one X (Twitter) account's voice. "
        "From the sample posts, produce a precise, reusable STYLE GUIDE that another "
        "writer could follow to write new posts indistinguishable in voice."
    )
    user = f"""Below are representative posts from @{TARGET} (engagement counts in brackets).

Produce a Markdown style guide with these sections:
1. **Voice & tone** — personality, attitude, point of view
2. **Structure** — how posts open, develop, and close; typical length; threads vs single
3. **Formatting** — line breaks, emoji/symbol use, lists, cashtags/hashtags
4. **Recurring themes & topics**
5. **Signature phrases / vocabulary**
6. **Do** — concrete rules that capture what makes the voice work
7. **Don't** — what to avoid to stay on-voice

Be specific and prescriptive. Write the guide in the same language the account writes in.

# Sample posts
{corpus}
"""
    client = Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Missing ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1

    uid = resolve_user_id(TARGET)
    print(f"@{TARGET} -> user id {uid}")
    tweets = fetch_tweets(uid)
    print(f"Fetched {len(tweets)} original tweets.")
    if not tweets:
        print("No tweets fetched.", file=sys.stderr)
        return 1

    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    with (STYLE_DIR / "source_tweets.jsonl").open("w", encoding="utf-8") as handle:
        for t in tweets:
            handle.write(json.dumps(t, ensure_ascii=False) + "\n")

    sample = select_sample(tweets)
    print(f"Distilling style from {len(sample)} representative tweets...")
    profile = distill(sample)

    REF.mkdir(parents=True, exist_ok=True)
    note = (
        f"<!-- Auto-generated by fetch_style.py from @{TARGET}. "
        "Do not edit by hand; re-run the 'learn style' workflow. -->\n\n"
    )
    (REF / "x-style-profile.md").write_text(
        note + f"# Style guide — learned from @{TARGET}\n\n" + profile + "\n",
        encoding="utf-8",
    )

    top = select_sample(tweets, limit=25, max_chars=20000)
    blocks = [f"<!-- Auto-generated from @{TARGET}. -->\n", f"# Example posts — @{TARGET}\n"]
    for i, t in enumerate(top, 1):
        m = t.get("public_metrics", {})
        blocks.append(
            f"## Example {i}  (♥{m.get('like_count', 0)} ↻{m.get('retweet_count', 0)})\n"
            f"{t.get('text', '').strip()}\n"
        )
    (REF / "x-style-examples.md").write_text("\n".join(blocks), encoding="utf-8")

    print("Wrote x-manager/reference/x-style-profile.md and x-style-examples.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
