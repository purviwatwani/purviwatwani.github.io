"""Pulls Letterboxd films + Goodreads currently-reading into data/*.json. Standard library only."""
import json, os, re, sys, html as htmlmod, urllib.request
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from datetime import datetime

LB_USER = "purviews"
GOODREADS_ID = "155996055"   # the number in your profile link, e.g. 12345678
GOODREADS_SHELF = "currently-reading"
SUBSTACK_PUB = "purview23"                    # purview23.substack.com

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def parse_letterboxd(xml_text):
    ns = {"lb": "https://letterboxd.com"}
    root = ET.fromstring(xml_text)
    films, seen = [], set()
    for it in root.iter("item"):
        t = it.find("lb:filmTitle", ns)
        if t is None:            # skip lists and other non-film items
            continue
        title = t.text
        year = it.findtext("lb:filmYear", default="", namespaces=ns)
        if (title, year) in seen:
            continue
        seen.add((title, year))
        rating = it.find("lb:memberRating", ns)
        wd = it.find("lb:watchedDate", ns)
        watched = ""
        if wd is not None and wd.text:
            try: watched = datetime.strptime(wd.text, "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")
            except ValueError: watched = wd.text
        m = re.search(r'<img[^>]+src="([^"]+)"', it.findtext("description") or "")
        films.append({"title": title, "year": year, "rating": float(rating.text) if rating is not None else None,
                      "watched": watched, "poster": m.group(1) if m else ""})
        if len(films) >= 12:
            break
    return {"profile": f"https://letterboxd.com/{LB_USER}/", "films": films}

def parse_goodreads(xml_text):
    root = ET.fromstring(xml_text)
    books = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        cover = (it.findtext("book_large_image_url") or it.findtext("book_image_url") or "").strip()
        books.append({"title": title, "author": (it.findtext("author_name") or "").strip(), "cover": cover})
        if len(books) >= 8:
            break
    return {"profile": f"https://www.goodreads.com/user/show/{GOODREADS_ID}", "books": books}

def letterboxd():
    return parse_letterboxd(get(f"https://letterboxd.com/{LB_USER}/rss/"))

def goodreads():
    if GOODREADS_ID.startswith("PUT_"):
        raise RuntimeError("set GOODREADS_ID at the top of scripts/sync.py")
    url = f"https://www.goodreads.com/review/list_rss/{GOODREADS_ID}?shelf={GOODREADS_SHELF}"
    return parse_goodreads(get(url))

def clean(text, n=170):
    t = re.sub(r"<[^>]+>", " ", text or "")
    t = re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"

def kind_of(title):
    return "weeknote" if re.search(r"week\s*-?\s*notes?", title, re.I) else "article"

def substack():
    base = f"https://{SUBSTACK_PUB}.substack.com"
    posts = []
    try:                                       # full archive (newest first)
        offset = 0
        while offset < 150:
            items = json.loads(get(f"{base}/api/v1/archive?sort=new&search=&offset={offset}&limit=25"))
            for p in items:
                if p.get("type") == "thread" or not p.get("title"):
                    continue
                posts.append({"title": p["title"], "desc": clean(p.get("subtitle") or p.get("description")),
                              "url": p.get("canonical_url") or f"{base}/p/{p.get('slug')}",
                              "date": (p.get("post_date") or "")[:10], "paid": p.get("audience") == "only_paid"})
            if len(items) < 25:
                break
            offset += 25
    except Exception as e:
        print("substack archive failed, trying RSS:", e, file=sys.stderr)
    if not posts:                              # fallback: latest posts from the RSS feed
        for it in ET.fromstring(get(f"{base}/feed")).iter("item"):
            try: d = parsedate_to_datetime(it.findtext("pubDate")).strftime("%Y-%m-%d")
            except Exception: d = ""
            posts.append({"title": it.findtext("title") or "", "desc": clean(it.findtext("description")),
                          "url": it.findtext("link") or "", "date": d, "paid": False})
    old = []
    if os.path.exists("data/articles.json"):   # keep older posts even if they fall out of the feed
        try: old = json.load(open("data/articles.json", encoding="utf-8")).get("posts", [])
        except Exception: pass
    merged = {p["url"]: p for p in old + posts if p.get("url")}
    out = sorted(merged.values(), key=lambda p: p.get("date", ""), reverse=True)[:150]
    for p in out:
        p["kind"] = kind_of(p["title"])
    return {"profile": base, "posts": out}

if __name__ == "__main__":
    for name, fn, key in (("letterboxd", letterboxd, "films"), ("books", goodreads, "books"), ("articles", substack, "posts")):
        try:
            data = fn()
            if data[key]:
                save(f"data/{name}.json", data); print(name, "ok:", len(data[key]))
            else:
                print(name, "returned nothing; keeping old file", file=sys.stderr)
        except Exception as e:
            print(name, "failed:", e, file=sys.stderr)
