"""Parse the festival website (dxfest.com) into data/web.json.

Inputs (raw/web/, gitignored):
  rest/speakers-*.json, rest/conference-*.json  WordPress REST dumps
  films/<slug>.html, conference/<slug>.html       rendered pages
  media.json                                      featured-media id -> image URL
"""
import glob
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "web"

BOILER_END = {"PURCHASE A TICKET", "RSVP A FREE TICKET", "BUY A FESTIVAL PASS", "BUY TICKETS",
              "Twitter", "GET TICKETS", "WATCH NOW", "RSVP"}
MENU_LAST = {"Volunteer"}


def text_lines(h):
    m = re.search(r"<body.*", h, re.S)
    t = m.group(0) if m else h
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</(p|div|h\d|li|section|span)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()]


def body_lines(L):
    """Lines between the site menu and the footer."""
    start = 0
    for i, l in enumerate(L):
        if l in MENU_LAST:
            start = i + 1
            break
    out = []
    for l in L[start:]:
        if l in BOILER_END or l.startswith("(202) 683") or l.startswith("© Copyright"):
            break
        out.append(l)
    return out


def clean_html_text(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</p>\s*", "\n\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def og(h, prop):
    m = re.search(r'<meta property="%s" content="([^"]*)"' % re.escape(prop), h)
    return html.unescape(m.group(1)) if m else None


def parse_film(path):
    h = open(path, encoding="utf-8", errors="replace").read()
    slug = Path(path).stem
    years = re.findall(r"film-year-(\d{4})-films", h)
    flags = set(re.findall(r"film-year-(opening|closing|centerpiece|spotlight|yr-impact-screenings?)\b", h))
    ftype = re.findall(r"film-type-(short|full-feature-film)", h)
    L = body_lines(text_lines(h))
    # Title repeated twice at the top (heading + hero)
    title = og(h, "og:title") or (L[0] if L else slug)
    title = re.sub(r"(\s+-\s+|:\s*)Double Exposure.*$", "", title).strip()
    pre = re.match(r"^(opening night(?: film)?|closing night(?: film)?|centerpiece(?: film)?|spotlight(?: film)?)\s*:\s*", title, re.I)
    if pre:
        flags_from_title = pre.group(1).lower().split()[0]
        title = title[pre.end():]
    else:
        flags_from_title = None
    title = re.sub(r"\s+library screening$", "", title, flags=re.I).strip()
    if title.isupper() and len(title.split()) >= 3:
        small = {"a", "an", "the", "of", "and", "in", "on", "for", "to", "at", "by", "vs.", "vs"}
        ws = title.lower().split()
        title = " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(ws))
    i = 0
    q = lambda t: html.unescape(t).replace("\u2019", "'").replace("\u2018", "'").lower()
    while i < len(L) and i < 3 and (q(L[i]) == q(title) or (i < 2 and len(L[i]) < 80 and not L[i].endswith(".") and L[i].replace("1917", "1971") == title)):
        i += 1
    rest = L[i:]
    meta = {}
    syn = []
    for l in rest:
        m = re.match(r"^(COUNTRY|COUNTRIES|YEAR|RUNTIME|LANGUAGE|LANGUAGES|PREMIERE)\s*:\s*(.*)$", l, re.I)
        if m:
            meta[m.group(1).upper()] = m.group(2).strip()
        else:
            syn.append(l)
    director = None
    if syn and len(syn[0]) < 120 and not syn[0].endswith("."):
        director = re.sub(r"^(Dirs?\.|Directed by|Director:?)\s*", "", syn.pop(0), flags=re.I).strip()
    rt = re.search(r"(\d+)", meta.get("RUNTIME", "") or "")
    fy = re.search(r"(\d{4})", meta.get("YEAR", "") or "")
    if flags_from_title:
        flags.add({"opening": "opening", "closing": "closing", "centerpiece": "centerpiece", "spotlight": "spotlight"}[flags_from_title])
    if "short-strand" in slug and years:
        years = [max(years)]
    if fy and years:
        years = [y for y in years if int(y) >= int(fy.group(1))] or years
    img = og(h, "og:image")
    if img and ("bg-widescreen" in img or "DX-FEST" in img or "logo" in img.lower()):
        img = None
    return {
        "slug": slug,
        "url": f"https://dxfest.com/films/{slug}/",
        "title": html.unescape(title),
        "festival_years": sorted({int(y) for y in years}),
        "slot_flags": sorted(flags),
        "is_short": ftype == ["short"] if ftype else None,
        "director_line": director,
        "country": meta.get("COUNTRY") or meta.get("COUNTRIES"),
        "film_year": int(fy.group(1)) if fy else None,
        "runtime_min": int(rt.group(1)) if rt else None,
        "synopsis": "\n\n".join(syn).strip(),
        "image": img,
    }


DATE_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})$")
TIME_RE = re.compile(r"^\d{1,2}(:\d{2})?\s*[ap]m$", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}


VENUE_WORDS = (r"librar|center|centre|hotel|theat|gallery|club|building|museum|\bhall\b|\broom\b|archives|online|cinema|"
               r"auditorium|floor|cafe|habit|loft|university|school|church|virtual|zoom|studio|\bspace\b|street|avenue")


def parse_session_page(path):
    h = open(path, encoding="utf-8", errors="replace").read()
    L = body_lines(text_lines(h))
    if L and L[0].lower().startswith("back to"):
        L = L[1:]
    speakers = []
    for s in re.findall(r'href="https://dxfest.com/speakers/([a-z0-9-]+)/"', h):
        if s not in speakers:
            speakers.append(s)
    out = {"speaker_slugs": speakers, "date": None, "time": None, "end_time": None, "venue": None}
    title = L[0] if L else None
    rest = L[1:]
    k = 0
    if k < len(rest) and DATE_RE.match(rest[k]):
        m = DATE_RE.match(rest[k])
        out["date"] = "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(1)], int(m.group(2)))
        k += 1
    if k < len(rest) and TIME_RE.match(rest[k]):
        out["time"] = rest[k]
        k += 1
    if k < len(rest) and rest[k].startswith("-"):
        out["end_time"] = rest[k].lstrip("- ").strip() or None
        k += 1
    if k < len(rest) and len(rest[k]) < 90 and re.search(VENUE_WORDS, rest[k], re.I):
        out["venue"] = rest[k]
    vids = re.findall(r'(https?://(?:www\.)?(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/|player\.vimeo\.com/video/|vimeo\.com/)[A-Za-z0-9_\-]+)', h)
    out["videos"] = sorted(set(vids))
    out["page_title"] = title
    return out


def main():
    media = {int(k): v for k, v in json.load(open(RAW / "media.json")).items()}
    # speakers
    speakers = []
    for f in sorted(glob.glob(str(RAW / "rest" / "speakers-*.json"))):
        for r in json.load(open(f)):
            cats = [c[len("speakers-"):] for c in r["class_list"] if c.startswith("speakers-")]
            years = sorted({int(m) for c in cats for m in re.findall(r"(20\d\d)", c)})
            speakers.append({
                "wp_id": r["id"], "slug": r["slug"], "url": r["link"],
                "name": html.unescape(r["title"]["rendered"]).strip(),
                "bio": clean_html_text(r["content"]["rendered"]),
                "categories": cats, "years": years, "created": r["date"][:10],
                "photo": media.get(r["featured_media"]),
            })
    # sessions
    st = {670: 2016, 664: 2018, 638: 2019, 554: 2020, 291: 2021, 307: 2022, 319: 2023, 328: 2024, 944: 2025, 1713: 2026}
    kinds = {533: "dx-squared", 289: "film-screening", 290: "session", 288: "workshop"}
    days = {281: 1, 282: 2, 283: 3, 284: 4, 285: 5}
    sessions = []
    for f in sorted(glob.glob(str(RAW / "rest" / "conference-*.json"))):
        for r in json.load(open(f)):
            types = r.get("session-type") or []
            year = next((st[t] for t in types if t in st), None)
            s = {
                "wp_id": r["id"], "slug": r["slug"], "url": r["link"],
                "title": html.unescape(r["title"]["rendered"]).strip(),
                "description": clean_html_text(r["content"]["rendered"]),
                "year": year, "kinds": [kinds[t] for t in types if t in kinds],
                "day": next((days[d] for d in (r.get("session-days") or []) if d in days), None),
                "created": r["date"][:10],
            }
            p = RAW / "conference" / (r["slug"] + ".html")
            if p.exists():
                s.update(parse_session_page(p))
            if not s["year"] and s.get("date"):
                s["year"] = int(s["date"][:4])
            sessions.append(s)
    films = [parse_film(p) for p in sorted(glob.glob(str(RAW / "films" / "*.html")))]
    out = {"speakers": speakers, "sessions": sessions, "films": films}
    (ROOT / "data").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "data" / "web.json", "w"), indent=1, ensure_ascii=False)
    print(f"speakers {len(speakers)}  sessions {len(sessions)}  films {len(films)}")


if __name__ == "__main__":
    main()
