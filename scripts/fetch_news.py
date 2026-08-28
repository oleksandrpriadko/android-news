#!/usr/bin/env python3
"""Fetch Android/Kotlin dev blog RSS feeds and post new items to Slack."""

import html
import json
import os
import re
import sys
import time

import feedparser
import requests

FEEDS = {
    "Android Developers Blog": "https://android-developers.googleblog.com/feeds/posts/default",
    "Kotlin Blog": "https://blog.jetbrains.com/kotlin/feed/",
}

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
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

    On the very first run (empty state), every current entry is recorded as
    seen but nothing is posted — otherwise the bot would dump each feed's
    entire backlog into Slack the moment it's enabled.
    """
    seen_ids = set(state.get("posted_ids", []))
    first_run = not seen_ids
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
            if first_run:
                continue
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


def post_to_slack(webhook_url, items, batch_size=SLACK_BATCH_SIZE):
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        payload = build_slack_payload(batch)
        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()


def main():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("error: SLACK_WEBHOOK_URL is not set", file=sys.stderr)
        return 1

    state = load_state(STATE_FILE)
    was_first_run = not state.get("posted_ids")

    new_items, newly_seen_ids = fetch_new_items(state)

    if new_items:
        post_to_slack(webhook_url, new_items)
        print(f"Posted {len(new_items)} new item(s) to Slack.")
    elif was_first_run:
        print("First run: seeded state with existing feed items, nothing posted.")
    else:
        print("No new items.")

    if newly_seen_ids:
        posted_ids = state.get("posted_ids", []) + newly_seen_ids
        state["posted_ids"] = posted_ids[-MAX_TRACKED_IDS:]
        save_state(STATE_FILE, state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
