# Reddit posts (post by hand)

Six posts, each written for one subreddit. Post them a couple of days apart in
this order: the first three are general tips that build karma and trust, the
next two present your products, and the last is an optional tip.

**Rewrite each post in your own words before posting.** r/webdev, r/ereader and
r/kindle remove AI-written posts, and Reddit readers spot that tone fast. Treat
these as outlines with the facts checked: keep the facts, change the wording.

Before each one: read the subreddit's sidebar rules (they change, and I could
only check them through third-party snapshots), and pick a flair if the sub asks
for one. Lines marked **[check]** need you to confirm a detail only you know.

After posting: reply to every comment for the first few hours. On Reddit the
comment thread is the post.

---

## 1. r/Calibre: tip (no link)

**Rules:** couldn't be confirmed (Reddit blocks my tools). Reportedly troubleshooting guides do well and blatant self-promotion gets downvoted. Read the sidebar first.

**Title**

Tip: if a scanned PDF converts to an almost empty EPUB, the text is probably in an invisible OCR layer

**Body**

Scanned PDFs often carry their recognized text as an invisible layer on top of the page images. That's why you can search and copy text in them.

Calibre's PDF input skips invisible text, so a scanned book like this can come out as an EPUB with almost no words in it.

How to tell if this is what's happening:

- Search the PDF for a word. If search works but the EPUB is nearly empty, it's this.
- Or, with Poppler installed: `pdftotext book.pdf - | wc -c`. A big number means the text is there.

Workaround if you only need the text: `pdftotext -layout book.pdf book.txt`, then convert the TXT in Calibre. You lose images and formatting, but you get the words.

(Disclosure: I build a PDF to EPUB converter, so I spend a lot of time with files like these. Happy to answer questions.)

---

## 2. r/ffmpeg: heads-up (no link)

**Rules:** couldn't be confirmed. A detailed FFmpeg tip is on-topic. Read the sidebar first.

**Title**

Heads-up: FFmpeg treats %d in a path as a frame pattern, even in folder names (and in input file names on 6.1)

**Body**

If you run FFmpeg on files your users named, this is worth knowing:

- **Output:** if the output path contains `%d` anywhere, including in a folder name, FFmpeg treats it as an image-sequence pattern.
- **Input:** FFmpeg 6.1 reads an input file named `100%done.png` the same way.

Names like "100% final.png" are easy to come across.

What works: give FFmpeg plain relative file names, so a `%` elsewhere in the path never reaches it. **[check: describe your approach in one line, e.g. "run FFmpeg with its working directory set to the file's folder"]**

There's also `-pattern_type none` for image inputs and `-update 1` for single-image outputs. Does anyone have a cleaner general approach?

---

## 3. r/webdev: how-to (no link)

**Rules:** no commercial promotion (rule 4), project sharing only on Showoff Saturday with the right flair (rule 5), and LLM-written posts are removed (rule 8). This post names no product, so it can go any day, but it must be in your own words.

**Title**

How I got a site from 120 !important declarations down to zero

**Body**

One of my sites had built up 10,650 lines of CSS across 5 files, with 120 `!important` declarations. After a redesign it's 2,787 lines and zero `!important`.

How it builds up: a rule hides or overrides something too broadly, say with a `parent > child` selector, and catches an element it shouldn't. A quick `!important` fixes that element. Then the next override needs another one.

What got it to zero: **[check: one or two lines on how, e.g. "moved to Tailwind utilities plus a small token file"]**

What I'd pass on:

- Structural selectors used to hide things eventually hit the wrong element. Remove the markup instead.
- Every `!important` makes the next one more likely.
- If you're scared to delete CSS, that's the sign to rebuild it.

How do you keep `!important` from creeping back in?

---

## 4. r/SideProject: LaunchOrbit (link)

**Rules:** no written restrictions found. Sharing your own project is what the sub is for; say it's yours and ask for feedback.

**Title**

I built a launch board where money can't buy the top spot. Every product is a tile in one big spiral

**Body**

I built LaunchOrbit, a launch board for indie products where the top spot can't be bought:

- Every product is a tile on one shared canvas you can pan and zoom.
- Tiles are packed in a spiral, with #1 in the middle.
- Only community upvotes decide the order. Paid plans get a bigger tile, never a better position.
- Listing is free: paste your URL and it pulls in your logo.

Some build notes for the curious:

- The spiral packer keeps an occupancy bitmap and only tries spots along the edges of tiles already placed. 10,000 tiles pack in about 90 ms.
- Panning holds 120 fps with 8,500 tiles on the canvas.
- Fetching a logo from any URL someone pastes is a classic SSRF risk, so the fetcher blocks private and cloud-metadata IPs and re-checks DNS on every redirect.

It's at launchorbit.co. I'd love feedback: what would make a board like this more useful for discovering products?

---

## 5. r/ereader: Convert2EPUB (link)

**Rules:** rule 5: no advertising commercial products **without prior approval from the moderators**. Also no AI content and no blogspam links. Send the modmail below first and post only after they say yes.

**Modmail to send first** (r/ereader → Message the mods)

> Hi, I'm the developer of Convert2EPUB, a PDF to EPUB converter built for scanned books, illustrated books and maths. Rule 5 asks for approval before posting about a commercial product, so I'm asking first. I'd like to post a short text write-up of how it works and invite readers to try it on their hardest PDFs. Ordinary text PDFs convert free with no account. Would that be OK? Happy to adjust the post to fit the sub.

**Title**

I built a PDF to EPUB converter for the hard cases: scanned books, illustrated books and maths. Send me your toughest PDFs

**Body**

Disclosure up front: I'm the developer.

PDFs are hard to read on an e-reader: fixed pages, tiny text, zoom and scroll on every line. EPUB fixes that because the text reflows to fit your screen. Convert2EPUB is built for the PDFs that are hardest to convert:

- **Scans:** it reads the hidden OCR text if the PDF has it, and runs OCR if it doesn't.
- **Illustrated books:** pictures and photos stay in place in the reflowed text.
- **Maths:** formulas are kept as images inside the reflowed text, so equations stay readable.
- **Structure:** real chapters, a working table of contents, and valid EPUB 3 output.
- **Fallback:** if a PDF can't be reflowed, you get a fixed-layout EPUB instead.

Ordinary text PDFs convert free, with no account and no page limit. OCR pages use credits, and the first 10 are free.

It's at convert2epub.com. If you have a PDF you've never managed to read comfortably on your e-reader, try it and tell me how it turned out.

---

## 6. r/Supabase: tip (optional, no link)

**Rules:** posts must "seek help, share knowledge, or provide constructive feedback", and titles must describe the actual issue. Posts from low-karma accounts may be held; message the mods if yours doesn't appear.

**Title**

PSA: a local config.toml points login redirects to 127.0.0.1 by default. Check your live Auth settings after pushing config

**Body**

A local `supabase/config.toml` sets `site_url` and `additional_redirect_urls` to 127.0.0.1 by default. If that config gets pushed to your hosted project, those values come with it, and magic links start sending users to localhost.

Worth doing:

- After pushing config, check Authentication → URL Configuration in the dashboard.
- Keep production URLs in `config.toml` behind an environment variable, or don't push auth config from your local machine at all.

Has anyone found a cleaner setup for keeping local and production auth settings apart?

---

## Comments: where most of the value is

Once a week, search r/kindle, r/kobo and r/ereader for "PDF" and sort by new. People ask how to read PDFs on their e-reader all the time. Answer the question properly first, and mention Convert2EPUB only when it directly solves their problem, saying you built it.

In r/kindle, don't name your product at all: rule 1 removes product promotion. Never touch DRM questions there either; rule 9 bans discussing DRM removal, including naming tools.

r/indiehackers allows one self-promotion post per user, with the Self Promotion flair. Save it for a launch.

## Don't

- Post the same text to several subreddits. Reddit's spam filter catches it and the account gets shadowbanned.
- Post links to your products in more than about 1 in 10 of your posts and comments.
- Use hashtags or marketing language. Reddit punishes both.
- Write about your products failing or having bugs. Share tips and what the products do.
