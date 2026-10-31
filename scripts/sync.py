"""Pulls Letterboxd + StoryGraph data into data/*.json. Standard library only."""
import json, re, html, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

LB_USER = "purviews"
SG_USER = "purviews"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def letterboxd():
    ns = {"lb": "https://letterboxd.com"}
    root = ET.fromstring(get(f"https://letterboxd.com/{LB_USER}/rss/"))
    films, seen = [], set()
    for it in root.iter("item"):
        t = it.find("lb:filmTitle", ns)
        if t is None:            # skip lists and other non-film items
            continue
        title = t.text
        year = (it.find("lb:filmYear", ns).text if it.find("lb:filmYear", ns) is not None else "")
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

def storygraph():
    page = get(f"https://app.thestorygraph.com/currently-reading/{SG_USER}")
    books = []
    for chunk in page.split("book-pane")[1:]:
        t = re.search(r'href="/books/[^"]+"[^>]*>\s*([^<\s][^<]*?)\s*</a>', chunk)
        a = re.search(r'href="/authors/[^"]+"[^>]*>\s*([^<]+?)\s*</a>', chunk)
        c = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        if t:
            books.append({"title": html.unescape(t.group(1)), "author": html.unescape(a.group(1)) if a else "",
                          "cover": c.group(1) if c else ""})
    return {"profile": f"https://app.thestorygraph.com/profile/{SG_USER}", "books": books}

for name, fn, key in (("letterboxd", letterboxd, "films"), ("storygraph", storygraph, "books")):
    try:
        data = fn()
        if data[key]:
            save(f"data/{name}.json", data); print(name, "ok:", len(data[key]))
        else:
            print(name, "returned nothing; keeping old file", file=sys.stderr)
    except Exception as e:
        print(name, "failed:", e, file=sys.stderr)
