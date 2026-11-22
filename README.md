# Social poster

Posts from `queue.toml` to X, Bluesky and LinkedIn on a schedule. It runs free on GitHub Actions; the only cost is X's per-post fee (about $0.015 a post, or $0.20 if the post contains a link).

## How it works

- You (or Claude) write posts into `queue.toml`.
- cron-job.org starts a run at 08:17, 09:47, 11:17, 12:47, 15:17, 19:17, 21:17 and 22:47 UTC by calling GitHub's API. GitHub's own scheduler is off.
- Each run posts what `SLOTS` in `poster.py` says for its hour:
  - **LaunchOrbit articles** at 08 and 19, **TrySEO articles** at 12. Articles come straight from each blog's sitemap, oldest unposted first, so a backlog catches up and new articles go out as they're published. They post to X (with the link) and Bluesky (as a link card). A post in `queue.toml` with id `launchorbit-blog-<slug>` and `kind = "article"` replaces the default title-and-description text.
  - **#connect posts** (`kind = "connect"`) at 11 and 21.
  - **Reach posts** (`kind = "reach"`) at 09, 15 and 22, and in the article slots when a blog has nothing new.
- X posts are at least 30 minutes apart, so a run that fires twice doesn't double post.
- What has been posted is recorded in `state/posted.json` and committed back to the repo, so nothing posts twice.
- A platform with no credentials is skipped, so you can start with one and add the others later.
- If a post fails, the run is marked failed and GitHub emails you. The next run retries it.

## One-time setup

### 1. Local config

```bash
cp .env.example .env
```

Fill in `.env` as you go through the steps below.

### 2. Bluesky (free, 2 minutes)

In Bluesky go to **Settings → Privacy and security → App passwords**, create one, and put your handle and that app password in `.env`.

### 3. X (pay-per-use)

1. Sign in at developer.x.com with the account you want to post from, create an app, and add some credits.
2. Under **User authentication settings**, set app permissions to **Read and write**. Any website and callback URL will do, for example `https://convert2epub.com`.
3. Under **Keys and tokens**, copy the API key and secret, then generate an access token and secret. Generate the token *after* step 2, or it will be read-only.

### 4. LinkedIn (free, personal profile)

1. At linkedin.com/developers, create an app. LinkedIn requires you to link it to a company page, so use your Convert2EPUB page.
2. On the **Products** tab, add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. On the **Auth** tab, add `http://localhost:8765/callback` as an authorized redirect URL, and copy the client ID and secret into `.env`.
4. Run `python3 linkedin_auth.py` and approve in the browser. It saves a token to `.env`.

The token lasts 60 days. The poster warns you 10 days before it expires; run `linkedin_auth.py` again then.

Posting as the company page instead of your profile needs LinkedIn's Community Management API, which requires an application and approval.

### 5. Test locally

```bash
python3 poster.py verify
python3 poster.py check
python3 poster.py run --dry-run
```

`verify` costs about a cent on X (it reads your profile). The others are free.

### 6. Put it on GitHub

Create a **private** repo, push this folder, then load your secrets:

```bash
gh secret set -f .env
```

To test, open **Actions → Post to social → Run workflow** in the repo. Manual runs are dry runs unless you untick the box.

To change what posts when, edit `SLOTS` in `poster.py`. To change the times, edit the jobs on cron-job.org.

## Day to day

- Add posts to `queue.toml` and push. Run `python3 poster.py check` first to catch posts that are too long.
- `draft = true` holds a post back. `date = 2026-11-03` holds it until that day.
- `python3 poster.py run --lane auto --hour 8 --dry-run` previews what a slot would post.
