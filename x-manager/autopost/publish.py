#!/usr/bin/env python3
"""Publish an approved draft to X (Twitter) via the v2 API using OAuth 1.0a.

The post text is read from the approval issue's body (passed in via the
ISSUE_BODY env var) and extracted from between the HTML-comment markers that
generate.py wrote. Credentials come from environment variables that the
workflow maps from repo secrets.
"""
import os
import re
import sys

API_URL = "https://api.x.com/2/tweets"
MARK_START = "<!--POST_START-->"
MARK_END = "<!--POST_END-->"
CRED_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


def extract_post(body):
    pattern = re.escape(MARK_START) + r"\s*(.*?)\s*" + re.escape(MARK_END)
    match = re.search(pattern, body, re.S)
    return match.group(1).strip() if match else None


def main():
    body = os.environ.get("ISSUE_BODY", "")
    text = extract_post(body)
    if not text:
        print("Could not find post text between markers in the issue body.", file=sys.stderr)
        return 1

    creds = {key: os.environ.get(key) for key in CRED_KEYS}
    missing = [key for key, value in creds.items() if not value]
    if missing:
        print(f"Missing X credentials: {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        from requests_oauthlib import OAuth1Session
    except ImportError:
        print("The 'requests_oauthlib' package is not installed.", file=sys.stderr)
        return 1

    oauth = OAuth1Session(
        creds["X_API_KEY"],
        client_secret=creds["X_API_SECRET"],
        resource_owner_key=creds["X_ACCESS_TOKEN"],
        resource_owner_secret=creds["X_ACCESS_TOKEN_SECRET"],
    )
    resp = oauth.post(API_URL, json={"text": text})
    if resp.status_code not in (200, 201):
        print(f"X API error {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    tweet_id = data.get("data", {}).get("id")
    url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "(unknown)"
    print(f"Posted: {url}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"tweet_url={url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
