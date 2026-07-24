import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from xml.sax.saxutils import escape as xml_escape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "seen.json")
RSS_FILE = os.path.join(SCRIPT_DIR, "deltarune_feed.xml")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def fetch_catalog():
    url = "https://a.4cdn.org/v/catalog.json"
    req = Request(url, headers={"User-Agent": "DeltaruneWatch/1.0 (github.com/USER/deltarune-watch)"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

KEYWORDS = [
    # Direct title matches
    "deltarune",
    # Character names specific to Deltarune (high confidence, no false positives)
    "spamton", "jevil", "ralsei", "berdly", "rouxl kaard",
    "mad mew mew", "tenna", "eram", "seam",
    # Character names that appear without "deltarune" on /v/
    "kris", "noelle", "susie", "asgore", "dess", "flowery",
    "catti", "rudy",
    # Dark world / lore terms
    "dark fountain", "dark world", "shadow crystal", "shadow mantle",
    "shelter", "angel heaven", "angels heaven",
    "castle town", "hometown", "weird route", "snowgrave",
    "proceeded", "proceeds", "roiling in code",
    "roaring knight", "thorn ring", "side b", "aborted route",
    "schizo bosses", "kriselle", "suselle", "krusie",
    # Chapter-specific terms
    "chapter 5", "chapter 6", "chapter 7",
    "flower girls", "gerson", "heartache",
    "rude buster", "dark sanctuary", "tv time", "black knife",
    "egg man", "man behind the tree", "noelle blog",
    "spamton sweepstakes", "keygen music", "big shot",
    # General Deltarune thread terms
    "deltarune chapter", "deltarune general",
    "deltarune theory", "deltarune lore", "deltarune news",
    "deltarune fanart", "deltarune meme", "deltarune ost",
]

def is_deltarune_thread(thread):
    com = thread.get("com", "").lower()
    sub = thread.get("sub", "").lower()
    text = com + " " + sub
    return any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in KEYWORDS)

def check_board():
    state = load_state()
    seen = set(state.get("seen", []))
    catalog = fetch_catalog()
    new_threads = []

    for page in catalog:
        for thread in page.get("threads", []):
            no = thread.get("no", 0)
            if no in seen:
                continue
            if is_deltarune_thread(thread):
                sub = thread.get("sub", "(no subject)")
                com = thread.get("com", "")
                seen.add(no)
                new_threads.append({
                    "id": no,
                    "title": sub[:200] if sub else "(no subject)",
                    "url": f"https://boards.4chan.org/v/thread/{no}/",
                    "time": int(thread.get("time", time.time())),
                    "preview": com[:500] if com else "",
                })

    if new_threads:
        save_state({"seen": list(seen)})
    generate_rss(new_threads)
    return new_threads

def generate_rss(new_threads):
    existing = ""
    if os.path.exists(RSS_FILE):
        with open(RSS_FILE, "r") as f:
            existing = f.read()

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []

    for t in new_threads:
        pub_date = datetime.fromtimestamp(t["time"], tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        desc = xml_escape(t["preview"][:500]) if t["preview"] else "New Deltarune thread"
        items.append(f"""    <item>
      <title>{xml_escape(t["title"])}</title>
      <link>{xml_escape(t["url"])}</link>
      <guid isPermaLink="true">{xml_escape(t["url"])}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{desc}</description>
    </item>""")

    if not new_threads:
        if existing:
            return
        items.append("""    <item>
      <title>No threads yet</title>
      <link>https://boards.4chan.org/v/</link>
      <guid>deltarune-watch-start</guid>
      <pubDate>{now}</pubDate>
      <description>No Deltarune threads found yet. The feed will update when a new thread is detected.</description>
    </item>""".replace("{now}", now))

    all_items = "\n".join(items)
    repo_url = "https://raw.githubusercontent.com/lrptm/deltarune-watch/main/deltarune_feed.xml"

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Deltarune Threads on /v/</title>
    <link>https://boards.4chan.org/v/</link>
    <description>New threads mentioning Deltarune on 4chan's /v/ board, checked hourly</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{repo_url}" rel="self" type="application/rss+xml"/>
{all_items}
  </channel>
</rss>"""

    with open(RSS_FILE, "w") as f:
        f.write(feed)

if __name__ == "__main__":
    new = check_board()
    if new:
        print(f"Found {len(new)} new Deltarune thread(s):")
        for t in new:
            print(f"  {t['title']} - {t['url']}")
    else:
        print("No new Deltarune threads found.")
