"""Pulls Letterboxd films + Goodreads currently-reading into data/*.json. Standard library only."""
import json, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

LB_USER = "purviews"
GOODREADS_ID = "155996055"   # the number in your profile link, e.g. 12345678
GOODREADS_SHELF = "currently-reading"

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

if __name__ == "__main__":
    for name, fn, key in (("letterboxd", letterboxd, "films"), ("books", goodreads, "books")):
        try:
            data = fn()
            if data[key]:
                save(f"data/{name}.json", data); print(name, "ok:", len(data[key]))
            else:
                print(name, "returned nothing; keeping old file", file=sys.stderr)
        except Exception as e:
            print(name, "failed:", e, file=sys.stderr)
