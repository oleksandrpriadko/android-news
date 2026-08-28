# Android Dev News → Slack Bot

Posts daily Android & Kotlin developer blog updates to a Slack channel, via a
scheduled GitHub Action. No database — dedupe state lives in a `state.json`
file the workflow commits back to the repo after each run.

## How it works

- [`.github/workflows/daily-news.yml`](.github/workflows/daily-news.yml) runs
  once a day on a cron schedule (and can also be triggered manually from the
  Actions tab).
- [`scripts/fetch_news.py`](scripts/fetch_news.py) fetches the RSS feeds below
  with `feedparser`, skips any entry already recorded in `state.json`,
  formats the new ones (title + link + short excerpt) into a Slack message,
  and posts it with `requests` via a Slack Incoming Webhook.
- When there are new items, the script also writes a
  `digests/YYYY-MM-DD.md` file with the full day's items, and the Slack
  message links to it — a new file each day, so there's a browsable archive
  in the repo beyond Slack's own history.
- After a successful run, the workflow commits the updated `state.json`
  (and that day's digest file, if any) so the next run knows what's already
  been posted.

### Sources

- [Android Developers Blog](https://android-developers.googleblog.com/feeds/posts/default)
- [Kotlin Blog](https://blog.jetbrains.com/kotlin/feed/) (JetBrains)

Add or remove feeds by editing the `FEEDS` dict at the top of
`scripts/fetch_news.py`.

### First run

On the very first run (empty `state.json`), the script records every entry
currently in each feed as "seen" but doesn't post anything — otherwise it
would dump each blog's entire backlog into Slack the moment the bot is
enabled. Every run after that only posts genuinely new items.

## Setup

1. **Create a Slack Incoming Webhook**
   - In Slack, go to <https://api.slack.com/apps> → **Create New App** → *From
     scratch*.
   - Under **Incoming Webhooks**, toggle it on and click **Add New Webhook to
     Workspace**, then pick the channel to post to.
   - Copy the generated webhook URL (looks like
     `https://hooks.slack.com/services/…`).

2. **Add the webhook as a repo secret**
   - In this repo: **Settings → Secrets and variables → Actions → New
     repository secret**.
   - Name: `SLACK_WEBHOOK_URL`
   - Value: the webhook URL from step 1.

3. **(Optional) Adjust the schedule**
   - The workflow runs at `0 13 * * *` (13:00 UTC) by default — edit the
     `cron` line in `.github/workflows/daily-news.yml` to change it.

4. **Trigger a test run**
   - Go to the **Actions** tab → **Daily Android/Kotlin Dev News** → **Run
     workflow**.
   - The first run should report "seeded state" and post nothing to Slack;
     subsequent runs post whatever's new since the last check.

## Running locally

```bash
pip install -r requirements.txt
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/…"
python scripts/fetch_news.py
```

This reads/writes `state.json` in the current directory, same as the
workflow does.
