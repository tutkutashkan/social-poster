#!/usr/bin/env python3
"""Post queued updates from queue.toml to X, Bluesky and LinkedIn.

  python3 poster.py check                     Validate the queue and show what posts next
  python3 poster.py run --dry-run             Show exactly what would be posted, post nothing
  python3 poster.py run                       Post the next due item to each platform
  python3 poster.py run --platforms bluesky   Limit a run to some platforms
  python3 poster.py run --lane extra          Only posts marked platforms = ["x"]
  python3 poster.py verify                    Test credentials without posting

Each run posts at most one item per platform. What has been posted is recorded
in state/posted.json, so a post never goes out twice to the same platform.
Uses only the Python standard library (3.11+).
"""

import argparse
import base64
import datetime as dt
import functools
import hashlib
import hmac
import html.parser
import json
import os
import re
import secrets
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
QUEUE_FILE = ROOT / "queue.toml"
STATE_FILE = ROOT / "state" / "posted.json"
USER_AGENT = "social-poster/1.0"

PLATFORMS = ("x", "bluesky", "linkedin")
LIMITS = {"x": 280, "bluesky": 300, "linkedin": 3000}
REQUIRED_ENV = {
    "x": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"],
    "bluesky": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
    "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"],
}

# X pay-per-use prices (USD) as of October 2026. Check the X developer console for current rates.
X_COST_PLAIN = 0.015
X_COST_WITH_LINK = 0.20

# LinkedIn API versions are monthly (YYYYMM) and each is supported for about a year.
DEFAULT_LINKEDIN_VERSION = "202606"

# Full URLs, plus bare domains like convert2epub.com that X and Bluesky also treat as links.
LINK_RE = re.compile(
    r"https?://[^\s]+"
    r"|(?<![\w@./-])(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|app|dev|ai|me|ly|so|xyz|info|blog)\b(?:/[^\s]*)?",
    re.IGNORECASE,
)
HASHTAG_RE = re.compile(r"(?<!\S)#(\w+)")
TRAILING_PUNCT = ".,;:!?)]}'\""


# ---------------------------------------------------------------- helpers

def load_env(path=ROOT / ".env"):
    """Read KEY=value lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set (add it to .env or your GitHub secrets)")
    return value


def log(message):
    print(message, flush=True)


def warn(message):
    # GitHub Actions turns ::warning:: lines into visible annotations on the run.
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "WARNING: "
    print(prefix + message, flush=True)


def http(method, url, *, headers=None, json_body=None, data=None, timeout=30):
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.headers, response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        raise RuntimeError(f"{method} {url.split('?')[0]} returned {e.code}: {detail}") from None


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_today():
    return dt.datetime.now(ZoneInfo(os.environ.get("POSTER_TIMEZONE", "UTC"))).date()


def strip_link_punct(url):
    return url.rstrip(TRAILING_PUNCT)


def find_links(text):
    """(start, end, url) for each link, with trailing punctuation excluded."""
    links = []
    for m in LINK_RE.finditer(text):
        raw = strip_link_punct(m.group(0))
        url = raw if raw.lower().startswith(("http://", "https://")) else "https://" + raw
        links.append((m.start(), m.start() + len(raw), url))
    return links


# ---------------------------------------------------------------- queue and state

def load_queue():
    if not QUEUE_FILE.exists():
        raise SystemExit(f"{QUEUE_FILE.name} not found")
    with QUEUE_FILE.open("rb") as f:
        posts = tomllib.load(f).get("post", [])
    seen = set()
    for i, post in enumerate(posts, 1):
        post_id = post.get("id")
        if not post_id:
            raise SystemExit(f"Post #{i} in {QUEUE_FILE.name} has no id")
        if post_id in seen:
            raise SystemExit(f"Duplicate post id in {QUEUE_FILE.name}: {post_id}")
        seen.add(post_id)
        unknown = set(post.get("platforms", PLATFORMS)) - set(PLATFORMS)
        if unknown:
            raise SystemExit(f"{post_id}: unknown platform(s) {sorted(unknown)}")
    return posts


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def post_date(post):
    value = post.get("date")
    if value is None or isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    return dt.date.fromisoformat(str(value))


def is_due(post, today):
    date = post_date(post)
    return not post.get("draft") and (date is None or date <= today)


def in_lane(post, lane):
    """The "extra" lane is only X-only posts; the "main" lane is everything else."""
    if lane is None:
        return True
    return (post.get("platforms") == ["x"]) == (lane == "extra")


def next_post(posts, state, platform, today, lane=None):
    for post in posts:
        if (platform in post.get("platforms", PLATFORMS)
                and platform not in state.get(post["id"], {})
                and in_lane(post, lane)
                and is_due(post, today)):
            return post
    return None


def minutes_since_last_post(state, platform):
    times = [platforms[platform]["posted_at"] for platforms in state.values() if platform in platforms]
    if not times:
        return None
    last = max(dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)
    return (dt.datetime.now(dt.timezone.utc) - last).total_seconds() / 60


def configured(platform):
    return all(os.environ.get(name) for name in REQUIRED_ENV[platform])


# ---------------------------------------------------------------- text per platform

def body_text(post, platform):
    return (post.get(platform) or post.get("text") or "").strip()


def with_link(text, link):
    return text if not link or link in text else f"{text}\n\n{link}"


def x_text(post):
    text = body_text(post, "x")
    return with_link(text, post.get("link")) if post.get("x_include_link") else text


def x_length(text):
    """X's weighted length: every link counts as 23, most CJK and emoji count as 2."""
    length, pos = 0, 0
    for start, end, _ in find_links(text):
        length += _x_weight(text[pos:start]) + 23
        pos = end
    return length + _x_weight(text[pos:])


def _x_weight(text):
    light = ((0, 0x10FF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))
    return sum(1 if any(lo <= ord(ch) <= hi for lo, hi in light) else 2 for ch in text)


def x_cost(text):
    return X_COST_WITH_LINK if find_links(text) else X_COST_PLAIN


def planned_text(post, platform):
    """The text as it will look in the worst case (link appended when no card can be made)."""
    if platform == "x":
        return x_text(post)
    return with_link(body_text(post, platform), post.get("link"))


def text_length(text, platform):
    return x_length(text) if platform == "x" else len(text)


def problems(post, platform):
    """Errors that would make the platform reject the post."""
    text = planned_text(post, platform)
    if not text:
        return [f"no text for {platform}"]
    poll = post.get("poll")
    if poll is not None:
        if post.get("platforms") != ["x"]:
            return ['polls only work on X, so set platforms = ["x"]']
        if not 2 <= len(poll) <= 4 or any(not o or len(o) > 25 for o in poll):
            return ["a poll needs 2 to 4 options of at most 25 characters"]
        if not 5 <= post.get("poll_minutes", 1440) <= 10080:
            return ["poll_minutes must be between 5 and 10080"]
    length = text_length(text, platform)
    if length > LIMITS[platform]:
        return [f"{platform} text is {length} characters, limit is {LIMITS[platform]}"]
    return []


# ---------------------------------------------------------------- link previews

class MetaParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.title, self._in_title = {}, "", False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content") and key not in self.meta:
                self.meta[key] = attrs["content"].strip()
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@functools.lru_cache(maxsize=None)
def fetch_preview(url):
    """Open Graph title, description and image for a link card, or None."""
    try:
        _, body = http("GET", url, headers={"Accept": "text/html"}, timeout=15)
    except Exception as e:
        warn(f"Could not load {url} for a link card: {e}")
        return None
    parser = MetaParser()
    parser.feed(body[:1_000_000].decode("utf-8", errors="replace"))
    meta = parser.meta
    title = meta.get("og:title") or meta.get("twitter:title") or parser.title.strip()
    if not title:
        return None
    image = meta.get("og:image") or meta.get("twitter:image")
    return {
        "title": title,
        "description": meta.get("og:description") or meta.get("description") or "",
        "image": urllib.parse.urljoin(url, image) if image else None,
    }


@functools.lru_cache(maxsize=None)
def fetch_image(url):
    headers, body = http("GET", url, timeout=20)
    content_type = (headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    return content_type, body


# ---------------------------------------------------------------- X

def oauth1_header(method, url, consumer_key, consumer_secret, token, token_secret,
                  params=None, nonce=None, timestamp=None):
    """OAuth 1.0a HMAC-SHA1 Authorization header. JSON bodies are not part of the signature."""
    def q(value):
        return urllib.parse.quote(str(value), safe="~")

    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    pairs = sorted((q(k), q(v)) for k, v in {**(params or {}), **oauth}.items())
    base = "&".join([method.upper(), q(url), q("&".join(f"{k}={v}" for k, v in pairs))])
    key = f"{q(consumer_secret)}&{q(token_secret)}"
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in sorted(oauth.items()))


def x_request(method, url, json_body=None):
    auth = oauth1_header(method, url, env("X_API_KEY"), env("X_API_SECRET"),
                         env("X_ACCESS_TOKEN"), env("X_ACCESS_TOKEN_SECRET"))
    _, body = http(method, url, headers={"Authorization": auth}, json_body=json_body)
    return json.loads(body)


def post_x(post):
    text = x_text(post)
    payload = {"text": text}
    if post.get("poll"):
        payload["poll"] = {"options": post["poll"], "duration_minutes": post.get("poll_minutes", 1440)}
    data = x_request("POST", "https://api.x.com/2/tweets", payload)["data"]
    return {"id": data["id"], "url": f"https://x.com/i/web/status/{data['id']}", "cost_usd": x_cost(text)}


def verify_x():
    user = x_request("GET", "https://api.x.com/2/users/me")["data"]
    return f"@{user['username']}"


# ---------------------------------------------------------------- Bluesky

def bluesky_session():
    host = os.environ.get("BLUESKY_PDS", "https://bsky.social").rstrip("/")
    _, body = http("POST", f"{host}/xrpc/com.atproto.server.createSession", json_body={
        "identifier": env("BLUESKY_HANDLE"), "password": env("BLUESKY_APP_PASSWORD")})
    session = json.loads(body)
    return host, {"Authorization": f"Bearer {session['accessJwt']}"}, session


def bluesky_facets(text):
    """Make links and hashtags clickable. Bluesky indexes facets by UTF-8 byte offset."""
    def byte_range(start, end):
        return {"byteStart": len(text[:start].encode()), "byteEnd": len(text[:end].encode())}

    facets = [{"index": byte_range(start, end),
               "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]}
              for start, end, url in find_links(text)]
    for m in HASHTAG_RE.finditer(text):
        tag = m.group(1)
        if not tag.isdigit() and len(tag) <= 64:
            facets.append({"index": byte_range(m.start(), m.end()),
                           "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]})
    return facets


def bluesky_card(host, auth, link):
    preview = fetch_preview(link)
    if not preview:
        return None
    external = {"uri": link, "title": preview["title"][:300], "description": preview["description"][:1000]}
    if preview["image"]:
        try:
            content_type, data = fetch_image(preview["image"])
            if len(data) > 1_000_000:
                warn("Link card image is over Bluesky's 1 MB limit; posting the card without it")
            else:
                _, body = http("POST", f"{host}/xrpc/com.atproto.repo.uploadBlob",
                               headers={**auth, "Content-Type": content_type}, data=data)
                external["thumb"] = json.loads(body)["blob"]
        except Exception as e:
            warn(f"Bluesky link card image failed, posting without it: {e}")
    return {"$type": "app.bsky.embed.external", "external": external}


def post_bluesky(post):
    host, auth, session = bluesky_session()
    text, link = body_text(post, "bluesky"), post.get("link")
    embed = bluesky_card(host, auth, link) if link else None
    if link and not embed:
        text = with_link(text, link)
    record = {"$type": "app.bsky.feed.post", "text": text, "createdAt": now_utc(),
              "langs": [post.get("lang", "en")]}
    facets = bluesky_facets(text)
    if facets:
        record["facets"] = facets
    if embed:
        record["embed"] = embed
    _, body = http("POST", f"{host}/xrpc/com.atproto.repo.createRecord", headers=auth, json_body={
        "repo": session["did"], "collection": "app.bsky.feed.post", "record": record})
    uri = json.loads(body)["uri"]
    return {"id": uri, "url": f"https://bsky.app/profile/{session['did']}/post/{uri.rsplit('/', 1)[1]}"}


def verify_bluesky():
    return "@" + bluesky_session()[2]["handle"]


# ---------------------------------------------------------------- LinkedIn

# LinkedIn's "little text" format: these characters must be escaped or the post gets cut off.
LINKEDIN_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def linkedin_escape(text):
    out, pos = [], 0
    for m in HASHTAG_RE.finditer(text):
        out.append(LINKEDIN_RESERVED.sub(r"\\\1", text[pos:m.start()]))
        out.append("{hashtag|\\#|" + LINKEDIN_RESERVED.sub(r"\\\1", m.group(1)) + "}")
        pos = m.end()
    out.append(LINKEDIN_RESERVED.sub(r"\\\1", text[pos:]))
    return "".join(out)


def linkedin_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": os.environ.get("LINKEDIN_VERSION", DEFAULT_LINKEDIN_VERSION),
        "X-Restli-Protocol-Version": "2.0.0",
    }


def linkedin_upload_image(token, owner, image_url):
    content_type, data = fetch_image(image_url)
    _, body = http("POST", "https://api.linkedin.com/rest/images?action=initializeUpload",
                   headers=linkedin_headers(token),
                   json_body={"initializeUploadRequest": {"owner": owner}})
    upload = json.loads(body)["value"]
    http("PUT", upload["uploadUrl"],
         headers={"Authorization": f"Bearer {token}", "Content-Type": content_type}, data=data)
    return upload["image"]


def linkedin_article(token, author, link):
    preview = fetch_preview(link)
    if not preview:
        return None
    article = {"source": link, "title": preview["title"][:400]}
    if preview["description"]:
        article["description"] = preview["description"][:4000]
    if preview["image"]:
        try:
            article["thumbnail"] = linkedin_upload_image(token, author, preview["image"])
        except Exception as e:
            warn(f"LinkedIn link card image failed, posting without it: {e}")
    return {"article": article}


def post_linkedin(post):
    token, author = env("LINKEDIN_ACCESS_TOKEN"), env("LINKEDIN_AUTHOR_URN")
    text, link = body_text(post, "linkedin"), post.get("link")
    content = linkedin_article(token, author, link) if link else None

    def send(text, content):
        payload = {
            "author": author,
            "commentary": linkedin_escape(text),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if content:
            payload["content"] = content
        headers, _ = http("POST", "https://api.linkedin.com/rest/posts",
                          headers=linkedin_headers(token), json_body=payload)
        return headers.get("x-restli-id")

    if content:
        try:
            urn = send(text, content)
        except RuntimeError as e:
            warn(f"LinkedIn rejected the link card, posting the link in the text instead: {e}")
            urn = send(with_link(text, link), None)
    else:
        urn = send(with_link(text, link), None)
    return {"id": urn, "url": f"https://www.linkedin.com/feed/update/{urn}/"}


def verify_linkedin():
    _, body = http("GET", "https://api.linkedin.com/v2/userinfo",
                   headers={"Authorization": f"Bearer {env('LINKEDIN_ACCESS_TOKEN')}"})
    return json.loads(body).get("name", "connected")


def check_linkedin_expiry(today):
    expires = os.environ.get("LINKEDIN_TOKEN_EXPIRES")
    if not expires or not os.environ.get("LINKEDIN_ACCESS_TOKEN"):
        return
    days = (dt.date.fromisoformat(expires) - today).days
    if days < 0:
        warn(f"LinkedIn token expired on {expires}. Run: python3 linkedin_auth.py")
    elif days <= 10:
        warn(f"LinkedIn token expires in {days} days ({expires}). Run: python3 linkedin_auth.py")


POSTERS = {"x": post_x, "bluesky": post_bluesky, "linkedin": post_linkedin}
VERIFIERS = {"x": verify_x, "bluesky": verify_bluesky, "linkedin": verify_linkedin}


# ---------------------------------------------------------------- commands

def show(post, platform):
    text = planned_text(post, platform)
    extra = f", ${x_cost(text):.3f}" if platform == "x" else ""
    if not configured(platform):
        extra += ", no credentials yet"
    log(f"--- {platform}: {post['id']} ({text_length(text, platform)}/{LIMITS[platform]} chars{extra})")
    if platform != "x" and post.get("link"):
        log(body_text(post, platform))
        log(f"[link card: {post['link']}]")
    else:
        log(text)
    if platform == "x" and post.get("poll"):
        log("[poll: " + " | ".join(post["poll"]) + f", {post.get('poll_minutes', 1440) // 60} h]")
    log("")


def cmd_check(args):
    posts, state, today = load_queue(), load_state(), local_today()
    errors = 0
    log(f"Today is {today} ({os.environ.get('POSTER_TIMEZONE', 'UTC')}). {len(posts)} posts in the queue.\n")
    for post in posts:
        date = post_date(post)
        status = "draft" if post.get("draft") else f"from {date}" if date else "anytime"
        cells, found = [], []
        for platform in post.get("platforms", PLATFORMS):
            text = planned_text(post, platform)
            done = platform in state.get(post["id"], {})
            cells.append(f"{platform} {'posted' if done else f'{text_length(text, platform)}/{LIMITS[platform]}'}")
            if not done:
                found += problems(post, platform)
        log(f"{post['id']:<36} {status:<16} {' | '.join(cells)}")
        for problem in found:
            log(f"  ERROR: {problem}")
        errors += len(found)
        x_body = body_text(post, "x")
        if ("x" in post.get("platforms", PLATFORMS) and "x" not in state.get(post["id"], {})
                and find_links(x_body) and not post.get("x_include_link")):
            log(f"  note: the X text contains a link, so it costs ${X_COST_WITH_LINK:.2f} instead of ${X_COST_PLAIN:.3f}")

    log("\nNext up:")
    for platform in PLATFORMS:
        post = next_post(posts, state, platform, today, "main")
        ready = "" if configured(platform) else "  (no credentials yet)"
        log(f"  {platform:<9} {post['id'] if post else 'nothing due'}{ready}")
    extra = next_post(posts, state, "x", today, "extra")
    left = sum(1 for p in posts if in_lane(p, "extra") and "x" not in state.get(p["id"], {}) and not p.get("draft"))
    log(f"  x (extra) {extra['id'] if extra else 'nothing due'}  ({left} X-only posts left)")
    check_linkedin_expiry(today)
    return 1 if errors else 0


def cmd_run(args):
    posts, state, today = load_queue(), load_state(), local_today()
    check_linkedin_expiry(today)
    failures = 0
    for platform in args.platforms or PLATFORMS:
        post = next_post(posts, state, platform, today, args.lane)
        # Extra-lane runs keep a minimum gap so late, bunched-up scheduled runs
        # don't fire several posts in a row. Main runs always post, so X and
        # Bluesky stay in step on shared posts.
        min_gap = int(os.environ.get(f"{platform.upper()}_MIN_GAP_MINUTES", "0"))
        since = minutes_since_last_post(state, platform)
        if args.lane == "extra" and min_gap and since is not None and since < min_gap:
            log(f"{platform}: last post was {since:.0f} min ago (minimum gap {min_gap}), skipping")
            continue
        if not configured(platform) and not args.dry_run:
            log(f"{platform}: no credentials, skipping")
            continue
        if not post:
            log(f"{platform}: nothing due")
            continue
        if problems(post, platform):
            failures += 1
            warn(f"{platform}: not posting {post['id']}: {'; '.join(problems(post, platform))}")
            continue
        if args.dry_run:
            show(post, platform)
            continue
        try:
            result = POSTERS[platform](post)
        except Exception as e:
            failures += 1
            warn(f"{platform}: failed to post {post['id']}: {e}")
            continue
        state.setdefault(post["id"], {})[platform] = {**result, "posted_at": now_utc()}
        save_state(state)  # save after every success so a later failure can't cause a double post
        log(f"{platform}: posted {post['id']} -> {result['url']}")
    return 1 if failures else 0


def cmd_verify(args):
    failures = 0
    for platform in args.platforms or PLATFORMS:
        if not configured(platform):
            log(f"{platform:<9} no credentials")
            continue
        try:
            log(f"{platform:<9} OK, posting as {VERIFIERS[platform]()}")
        except Exception as e:
            failures += 1
            log(f"{platform:<9} FAILED: {e}")
    check_linkedin_expiry(local_today())
    return 1 if failures else 0


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Post queued updates to X, Bluesky and LinkedIn.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate queue.toml and show what posts next")
    for name, help_text in (("run", "post the next due item to each platform"),
                            ("verify", "test credentials without posting")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--platforms", type=lambda s: [x.strip() for x in s.split(",")],
                       help="comma-separated subset, e.g. bluesky,linkedin")
        if name == "run":
            p.add_argument("--dry-run", action="store_true", help="show what would be posted")
            p.add_argument("--lane", choices=["main", "extra"],
                           help='main: skip X-only posts; extra: only posts with platforms = ["x"]')
    args = parser.parse_args()
    if getattr(args, "platforms", None) and set(args.platforms) - set(PLATFORMS):
        parser.error(f"--platforms must be from: {', '.join(PLATFORMS)}")
    return {"check": cmd_check, "run": cmd_run, "verify": cmd_verify}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
