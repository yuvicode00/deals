# X autopost (scheduled draft → one-tap approve → publish)

Automated X (Twitter) posting built on **GitHub Actions**, with a human
approval gate. Nothing is ever posted without you adding a label.

## How it works

```
Daily cron (09:00 JST)
  └─ x-autopost-generate.yml
       ├─ pick the day's theme from themes.txt
       ├─ draft a post with the Claude API, following
       │  x-manager/reference/x-writing-guidelines.md + examples
       └─ open a GitHub Issue with the draft (label: x-draft)

You review the Issue on web/mobile
  └─ add the label "x-approve"          ← the one tap

x-autopost-publish.yml (on label)
  ├─ POST the text to the X API v2
  └─ comment the tweet URL and close the Issue
```

Only repo collaborators can add labels, so the `x-approve` label *is* the
authorization check.

## One-time setup

### 1. Get X API write access (paid)
Create an app in the [X Developer Portal](https://developer.x.com). Posting
requires **write** access — that is X's paid **Basic** tier; the free tier
cannot reliably post. Generate **OAuth 1.0a** keys with read+write permission.

### 2. Add repo secrets
`Settings → Secrets and variables → Actions → New repository secret`:

| Secret | Where it comes from |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com — used to draft posts |
| `X_API_KEY` | X app → Consumer Keys (API Key) |
| `X_API_SECRET` | X app → Consumer Keys (API Key Secret) |
| `X_ACCESS_TOKEN` | X app → Authentication Tokens (Access Token) |
| `X_ACCESS_TOKEN_SECRET` | X app → Authentication Tokens (Access Token Secret) |
| `X_ACCOUNT_PROFILE` *(optional)* | Free text describing your account/voice; improves tone |

Never commit these — they live only in GitHub secrets.

### 3. Merge to the default branch
GitHub's `schedule:` trigger only runs from the repository's **default
branch**. These workflows currently live on a feature branch — merge them to
`main` (or your default) for the daily cron to start. You can test before
merging with **Actions → "X autopost — generate draft" → Run workflow**
(also default-branch only).

### 4. Maintain the theme queue
Edit [`themes.txt`](./themes.txt) — one theme per line, `#` comments ignored.
A theme is chosen by rotating daily, so the queue is stateless; add or remove
lines whenever you like.

## Adjusting the schedule
Edit the `cron` in `.github/workflows/x-autopost-generate.yml`. It is in UTC
(`0 0 * * *` = 09:00 JST). Use [crontab.guru](https://crontab.guru) to build
other schedules.

## Caveats
- **Long posts need X Premium.** This writing style produces multi-paragraph
  posts that usually exceed 280 characters. The X API will reject posts over
  280 chars unless the account has **X Premium** (long-form). The review issue
  shows the character count so you can catch this before approving.
- **Stay within X's [automation policy](https://help.x.com/en/rules-and-policies/x-automation).**
- **Costs:** X API Basic (~$100/mo) + Claude API usage per draft.
- **Images are not handled here** — this pipeline posts text only. The
  plugin's `x-image` / `x-post` skills cover image posting via Supabase.
