#!/usr/bin/env python3
"""Fetch Android/Kotlin dev blog RSS feeds and post new items to Slack."""

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import feedparser
import requests

FEEDS = {
    "Android Developers Blog": "https://android-developers.googleblog.com/feeds/posts/default",
    "Kotlin Blog": "https://blog.jetbrains.com/kotlin/feed/",
}

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
DIGESTS_DIR = os.environ.get("DIGESTS_DIR", "digests")
MAX_TRACKED_IDS = 500
EXCERPT_LENGTH = 220
SLACK_BATCH_SIZE = 10


def load_state(path):
    if not os.path.exists(path):
        return {"posted_ids": []}
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"posted_ids": []}


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def clean_excerpt(raw_html, length=EXCERPT_LENGTH):
    text = re.sub(r"<[^>]+>", "", raw_html or "")
    text = html.unescape(text)
    text = " ".join(text.split())
    if len(text) > length:
        text = text[:length].rsplit(" ", 1)[0] + "…"
    return text


def entry_id(entry):
    return entry.get("id") or entry.get("link")


def entry_sort_key(entry):
    return entry.get("published_parsed") or entry.get("updated_parsed") or time.gmtime(0)


def fetch_new_items(state):
    """Return (new_items_to_post, ids_seen_this_run).

    If state.json is empty, every entry currently in each feed counts as
    new — the first run produces a digest of what's live right now instead
    of silently seeding.
    """
    seen_ids = set(state.get("posted_ids", []))
    new_items = []
    newly_seen = []

    for source, url in FEEDS.items():
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            print(f"warning: failed to fetch {source!r}: {parsed.bozo_exception}", file=sys.stderr)
            continue

        for entry in parsed.entries:
            eid = entry_id(entry)
            if not eid or eid in seen_ids:
                continue
            newly_seen.append(eid)
            new_items.append(
                {
                    "source": source,
                    "title": entry.get("title", "(untitled)"),
                    "link": entry.get("link", ""),
                    "excerpt": clean_excerpt(entry.get("summary", "")),
                    "sort_key": entry_sort_key(entry),
                }
            )

    new_items.sort(key=lambda item: item["sort_key"])
    return new_items, newly_seen


def render_digest_markdown(date_str, items):
    lines = [f"# Android/Kotlin dev news — {date_str}", ""]
    for item in items:
        lines.append(f"### [{item['title']}]({item['link']})")
        lines.append(f"*{item['source']}*")
        lines.append("")
        lines.append(item["excerpt"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_digest(date_str, items):
    os.makedirs(DIGESTS_DIR, exist_ok=True)
    path = os.path.join(DIGESTS_DIR, f"{date_str}.md")
    with open(path, "w") as f:
        f.write(render_digest_markdown(date_str, items))
    return path


def digest_url(path):
    """Build a link to the digest file on GitHub, if running inside Actions."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://github.com/{repo}/blob/{ref}/{path}"


def build_slack_payload(items):
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📱 Android/Kotlin dev news ({len(items)} new)"},
        }
    ]
    for item in items:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{item['link']}|{item['title']}>*\n_{item['source']}_\n{item['excerpt']}",
                },
            }
        )
    fallback_text = "\n".join(f"{item['title']} - {item['link']}" for item in items)
    return {"text": fallback_text, "blocks": blocks}


def post_to_slack(webhook_url, items, digest_link=None, batch_size=SLACK_BATCH_SIZE):
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    for i, batch in enumerate(batches):
        payload = build_slack_payload(batch)
        if digest_link and i == len(batches) - 1:
            payload["blocks"].append({"type": "divider"})
            payload["blocks"].append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"📄 Full digest saved to the repo: <{digest_link}|{digest_link}>"}],
                }
            )
        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()


def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    state = load_state(STATE_FILE)

    new_items, newly_seen_ids = fetch_new_items(state)

    if new_items:
        date_str = datetime.now(timezone.utc).date().isoformat()
        digest_file = write_digest(date_str, new_items)
        print(f"Wrote {len(new_items)} new item(s) to {digest_file}.")
        if webhook_url:
            post_to_slack(webhook_url, new_items, digest_link=digest_url(digest_file))
            print("Posted to Slack.")
    else:
        print("No new items.")

    if newly_seen_ids:
        posted_ids = state.get("posted_ids", []) + newly_seen_ids
        state["posted_ids"] = posted_ids[-MAX_TRACKED_IDS:]
        save_state(STATE_FILE, state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
