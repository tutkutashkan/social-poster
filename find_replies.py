#!/usr/bin/env python3
"""Find fresh X posts worth replying to, by hand.

  python3 find_replies.py              search, rank, write replies/<date>.md
  python3 find_replies.py --top 25     show more posts
  python3 find_replies.py --hours 24   only posts from the last 24 hours

Searches X through the treg CLI (https://treg.to, about $0.001 per search, so
a run costs under a cent) and ranks posts by how fast they are picking up
replies and views. It never posts anything: replying stays manual, because X
blocks API replies to people who didn't tag you and bans automated engagement.

Posts already listed in an earlier run are remembered in replies/seen.json and
skipped, so each run only shows new ones. The replies/ folder is not committed.
Needs the treg CLI, logged in (treg login).
"""

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "replies"
SEEN_FILE = OUT_DIR / "seen.json"
TOOL = "tikhub.x.twitter-web-fetch-search-timeline"
ME = "tskndev"

# (keyword, search type). Plain words and hashtags only: X search operators
# like lang: or since: don't survive this tool, so filtering happens below.
SEARCHES = [
    ("#connect #buildinpublic", "Latest"),
    ("#connect developers", "Latest"),
    ("#buildinpublic", "Top"),
    ("#indiehackers", "Latest"),
    ('"what are you building"', "Latest"),
    ("#SEO #buildinpublic", "Latest"),
]

MIN_FOLLOWERS, MAX_FOLLOWERS = 30, 50_000  # tiny accounts rarely see replies; huge ones bury them
MAX_REPLIES = 300                           # past this, a new reply sinks out of sight
# a post must mention one of these, which keeps news and politics out of the list
ON_TOPIC = ("#connect", "connect with", "build", "ship", "indie", "developer", "dev ", "founder",
            "saas", "startup", "seo", "launch", "side project", "product", "app ", "ai ")


def search(keyword, search_type):
    cmd = ["treg", "--json", "call", TOOL, "--query", f"keyword={keyword}", "--query", f"search_type={search_type}"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    try:
        answer = json.loads(out.stdout)
    except json.JSONDecodeError:
        print(f"  {keyword!r}: no answer ({out.stderr.strip()[:120]})", file=sys.stderr)
        return [], 0
    cost = answer.get("_treg", {}).get("charged_micro") or 0
    timeline = (((answer.get("result") or {}).get("data") or {}).get("timeline")) or []
    return [t for t in timeline if t.get("type") == "tweet"], cost


def age_hours(post, now):
    created = dt.datetime.strptime(post["created_at"], "%a %b %d %H:%M:%S %z %Y")
    return (now - created).total_seconds() / 3600


def score(post, hours):
    # engagement per hour, so a busy post from 2 hours ago beats a busier one from yesterday
    views = int(post.get("views") or 0)
    return (post.get("replies", 0) * 4 + post.get("favorites", 0) + views / 40) / (hours + 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=15, help="how many posts to list")
    parser.add_argument("--hours", type=float, default=36, help="skip posts older than this")
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()
    found, spent = {}, 0
    for keyword, search_type in SEARCHES:
        posts, cost = search(keyword, search_type)
        spent += cost
        for post in posts:
            found.setdefault(post["tweet_id"], (post, keyword))

    picks, authors = [], set()
    for post, keyword in found.values():
        user = post.get("user_info") or {}
        handle = post.get("screen_name", "")
        hours = age_hours(post, now)
        if (post["tweet_id"] in seen or handle.lower() == ME or handle in authors
                or hours > args.hours or post.get("lang") not in ("en", "qme", "zxx")
                or post["text"].startswith(("RT @", "@"))
                or not any(word in post["text"].lower() for word in ON_TOPIC)
                or not MIN_FOLLOWERS <= user.get("followers_count", 0) <= MAX_FOLLOWERS
                or post.get("replies", 0) > MAX_REPLIES):
            continue
        picks.append((score(post, hours), hours, post, keyword))
        authors.add(handle)
    picks.sort(key=lambda p: p[0], reverse=True)
    picks = picks[: args.top]

    lines = [f"# Reply list, {now:%Y-%m-%d %H:%M} UTC", "",
             f"{len(picks)} posts from the last {args.hours:g} hours, busiest first. "
             f"Searches cost ${spent / 1e6:.3f}.", ""]
    for n, (_, hours, post, keyword) in enumerate(picks, 1):
        user = post.get("user_info") or {}
        handle = post["screen_name"]
        text = " ".join(html.unescape(post["text"]).split())
        lines += [f"## {n}. @{handle} ({user.get('followers_count', 0):,} followers), {hours:.0f}h ago",
                  f"https://x.com/{handle}/status/{post['tweet_id']}", "",
                  f"{post.get('views') or 0} views, {post.get('replies', 0)} replies, "
                  f"{post.get('favorites', 0)} likes. Found by: {keyword}", "",
                  f"> {text[:400]}", ""]
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{now:%Y-%m-%d}.md"
    out.write_text("\n".join(lines))
    SEEN_FILE.write_text(json.dumps(sorted(seen | {p[2]["tweet_id"] for p in picks})))
    print(f"{len(found)} posts found, {len(picks)} listed in {out.relative_to(ROOT)}, cost ${spent / 1e6:.3f}")


if __name__ == "__main__":
    main()
