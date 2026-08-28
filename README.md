# Android Dev News Bot

Tracks daily Android & Kotlin developer blog updates via a scheduled GitHub
Action, and writes a daily digest file into this repo. No database — dedupe
state lives in a `state.json` file the workflow commits back after each run.
Slack posting is optional and off by default (see below).

## How it works

- [`.github/workflows/daily-news.yml`](.github/workflows/daily-news.yml) runs
  once a day on a cron schedule (and can also be triggered manually from the
  Actions tab).
- [`scripts/fetch_news.py`](scripts/fetch_news.py) fetches the RSS feeds below
  with `feedparser` and skips any entry already recorded in `state.json`.
- When there are new items, it writes a `digests/YYYY-MM-DD.md` file with
  the day's items (title + link + short excerpt) — one new file per day, so
  the repo builds up a browsable archive.
- After a successful run, the workflow commits the updated `state.json`
  (and that day's digest file, if any) so the next run knows what's already
  been recorded.
- **Optional:** if a `SLACK_WEBHOOK_URL` repo secret is set, the script also
  posts the new items to Slack and links back to that day's digest file. If
  the secret isn't set, this step is simply skipped — everything else still
  works.

### Sources

- [Android Developers Blog](https://android-developers.googleblog.com/feeds/posts/default)
- [Kotlin Blog](https://blog.jetbrains.com/kotlin/feed/) (JetBrains)

Add or remove feeds by editing the `FEEDS` dict at the top of
`scripts/fetch_news.py`.

### First run

On the very first run (empty `state.json`), the script records every entry
currently in each feed as "seen" but doesn't write a digest for them —
otherwise the very first run would dump each blog's entire backlog into the
repo. Every run after that only records genuinely new items.

## Setup

1. **(Optional) Adjust the schedule**
   - The workflow runs at `0 13 * * *` (13:00 UTC) by default — edit the
     `cron` line in `.github/workflows/daily-news.yml` to change it.

2. **Trigger a test run**
   - Go to the **Actions** tab → **Daily Android/Kotlin Dev News** → **Run
     workflow**.
   - The first run should report "seeded state" and write nothing;
     subsequent runs write a `digests/YYYY-MM-DD.md` for whatever's new
     since the last check.

That's it — no secrets are required to get digests committed to the repo.

### Enabling Slack posting (optional)

1. In Slack, go to <https://api.slack.com/apps> → **Create New App** → *From
   scratch* → enable **Incoming Webhooks** → **Add New Webhook to
   Workspace**, picking the channel to post to. Copy the webhook URL (looks
   like `https://hooks.slack.com/services/…`).
2. In this repo: **Settings → Secrets and variables → Actions → New
   repository secret** → name it `SLACK_WEBHOOK_URL` and paste the URL.
3. The next run will post new items to that channel in addition to writing
   the digest file.

## Running locally

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
```

Reads/writes `state.json` and `digests/` in the current directory, same as
the workflow does. Set `SLACK_WEBHOOK_URL` in your shell first if you also
want to test the Slack posting path.
