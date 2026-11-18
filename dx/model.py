"""Merge the catalogues (data/catalogues/<year>.json) and the website (data/web.json) into
data/festival.json: editions, films, sessions, people, topics, organisations, venues.
"""
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .topics import ORG_RX, TOPICS, orgs_for, topics_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

YEARS = list(range(2015, 2027))

CATALOGUE_PDF = {
    2015: "https://dxfest.com/wp-content/uploads/2020/02/2015DoubleExposure3AInvestigativeFilmFestival26Symposium.pdf",
    2016: "https://dxfest.com/wp-content/uploads/2020/02/2016DoubleExposureCatalog.pdf",
    2017: "https://dxfest.com/wp-content/uploads/2020/02/DX-2017-Catalog-Final.pdf",
    2018: "https://dxfest.com/wp-content/uploads/2020/02/DX_2018-Catalogue-Final.pdf",
    2019: "https://dxfest.com/wp-content/uploads/2020/02/Double-Exposure-catalog-2019-FINAL.pdf",
    2022: "https://dxfest.com/wp-content/uploads/2022/12/DXFest22-catalogue-5.pdf",
    2023: "https://dxfest.com/wp-content/uploads/2023/11/DXFest23-catalogue_spreads-final.pdf",
    2024: "https://dxfest.com/wp-content/uploads/2024/11/DX24-Catalog-Final.pdf",
    2025: "https://dxfest.com/wp-content/uploads/2026/03/DX25-Catalog-Final.pdf",
}
CATALOGUE_TS = {2015: "20261117014225", 2016: "20261117014250", 2017: "20261117014316", 2018: "20261117014342",
                2019: "2026", 2022: "20261117014408", 2023: "20261117014435", 2024: "20261117014501",
                2025: "20261117014527"}

# Editions with no catalogue: facts from the website and press coverage.
EDITION_FACTS = {
    2020: {"dates": "October 14–18, 2020", "format": "Online", "note": "Held online for the first time because of the COVID-19 pandemic."},
    2021: {"dates": "October 13–17, 2021", "format": "Online", "note": "Held online for a second year."},
    2026: {"dates": "November 5–8, 2026", "format": "In person", "theme": "Evidence in an age of doubt"},
}

NOT_SESSIONS = re.compile(r"^(lunch|breakfast|coffee|registration|break|networking break|check-?in|doors open|"
                          r"continental breakfast|coffee break|lunch break|happy hour|film screening: shortcuts)\b", re.I)
HONORIFIC = re.compile(r"^(dr|mr|mrs|ms|prof|professor|rev|sen|senator|rep|judge|hon|gen|col|lt|capt|maj)\.?\s+", re.I)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def slugify(s):
    s = strip_accents(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def name_key(n):
    n = strip_accents(n or "").strip()
    n = HONORIFIC.sub("", n)
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r",?\s+(jr|sr|ii|iii|iv|phd|md|esq)\.?$", "", n, flags=re.I)
    n = n.lower().replace("-", " ").replace("’", "'")
    n = re.sub(r"[^a-z' ]+", " ", n)
    toks = [t for t in n.split() if len(t) > 1 or t in ("x",)]
    return " ".join(toks)


def title_key(t):
    t = strip_accents(t or "").lower().replace("&", "and")
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def clean_name(n):
    n = re.sub(r"\s+", " ", (n or "").strip().strip(",;"))
    n = HONORIFIC.sub("", n) if HONORIFIC.match(n) and len(n.split()) > 2 else n
    if n.isupper() and len(n) > 3:
        n = " ".join(w.capitalize() if not re.match(r"^[A-Z]\.$", w) else w for w in n.split())
        n = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), n)
    return n


def split_names(s):
    if not s:
        return []
    s = re.sub(r"\s*\([^)]*\)", "", s)  # "(co-director)", "(uncredited)" ...
    s = re.sub(r"\b(Dirs?\.|Directed by|Director:?)\s*", "", s, flags=re.I)
    parts = re.split(r",\s*|\s+and\s+|\s*&\s*", s)
    return [clean_name(p) for p in parts if p.strip() and p.strip().lower() not in ("anonymous", "et al.")]


VENUE_CANON = [
    (r"bloomberg center", "Johns Hopkins University Bloomberg Center"),
    (r"martin luther king|mlk library", "Martin Luther King Jr. Memorial Library"),
    (r"naval heritage", "U.S. Naval Heritage Center"),
    (r"national union building", "National Union Building"),
    (r"eaton", "Eaton Hotel"),
    (r"dirty habit|hotel monaco|poste brasserie", "Hotel Monaco"),
    (r"national press club", "National Press Club"),
    (r"newseum", "Newseum"),
    (r"woolly mammoth", "Woolly Mammoth Theatre"),
    (r"national portrait gallery", "National Portrait Gallery"),
    (r"national geographic", "National Geographic Museum"),
    (r"national archives", "National Archives"),
    (r"district architecture", "District Architecture Center"),
    (r"loft at 600 f", "The Loft at 600 F"),
    (r"dcjcc|cafritz", "Edlavitch DC Jewish Community Center"),
    (r"avalon", "The Avalon Theatre"),
    (r"^online$|virtual", "Online"),
]


def venue_canon(v):
    if not v:
        return None
    for rx, name in VENUE_CANON:
        if re.search(rx, v, re.I):
            return name
    return re.sub(r"^the\s+", "", v.strip(), flags=re.I)


def load_aliases():
    p = DATA / "aliases.tsv"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "\t" in line:
                a, b = line.split("\t", 1)
                out[name_key(a)] = b.strip()
    return out


def load_not_people():
    p = DATA / "not_people.txt"
    return {name_key(l) for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")} if p.exists() else set()


ROLE_GROUP = {
    "director": "filmmaker", "co-director": "filmmaker", "producer": "filmmaker", "executive producer": "filmmaker",
    "co-producer": "filmmaker", "cinematographer": "filmmaker", "editor": "filmmaker", "filmmaker": "filmmaker",
    "writer": "filmmaker", "animator": "filmmaker", "composer": "filmmaker", "impact producer": "filmmaker",
    "moderator": "moderator", "host": "moderator", "facilitator": "moderator", "interviewer": "moderator",
    "panelist": "speaker", "speaker": "speaker", "presenter": "speaker", "discussant": "speaker", "guest": "speaker",
    "keynote": "keynote", "instructor": "trainer", "trainer": "trainer", "mentor": "trainer", "workshop leader": "trainer",
    "juror": "juror", "judge": "juror", "honoree": "honoree", "award recipient": "honoree", "recipient": "honoree",
    "subject": "subject", "journalist": "journalist", "reporter": "journalist", "fellow": "fellow", "pitch": "pitch",
}
ROLE_GROUP_LABEL = {
    "filmmaker": "Filmmakers", "moderator": "Moderators", "speaker": "Panelists & speakers", "keynote": "Keynote speakers",
    "trainer": "Workshop leaders", "juror": "Jurors", "honoree": "Honorees", "subject": "Film subjects",
    "journalist": "Journalists behind the films", "fellow": "Fellows", "pitch": "Pitch participants", "team": "Festival team",
}


def role_group(role):
    r = (role or "").lower().strip()
    if r in ROLE_GROUP:
        return ROLE_GROUP[r]
    for k, v in ROLE_GROUP.items():
        if k in r:
            return v
    return "speaker"


class People:
    def __init__(self):
        self.aliases = load_aliases()
        self.not_people = load_not_people()
        self.by_key = {}
        self.people = {}

    def resolve(self, name):
        name = clean_name(name)
        k = name_key(name)
        if not k or len(k) < 3 or k in self.not_people or " " not in k:
            return None
        if k in self.aliases:
            name = self.aliases[k]
            k = name_key(name)
        if k in self.by_key:
            return self.by_key[k]
        pid = slugify(name)
        base, n = pid, 2
        while pid in self.people:
            pid = f"{base}-{n}"
            n += 1
        self.people[pid] = {"id": pid, "name": name, "names": Counter(), "bios": [], "photo": None,
                            "appearances": [], "web_slugs": set(), "affiliations": Counter()}
        self.by_key[k] = pid
        return pid

    def add_name(self, pid, name):
        self.people[pid]["names"][clean_name(name)] += 1


def merge_similar_people(P, refs):
    """Merge 'Ramona Diaz' into 'Ramona S. Diaz' etc: same first token, one name's tokens a subset of the other's."""
    keys = list(P.by_key.items())
    tokens = {k: k.split() for k, _ in keys}
    by_first = defaultdict(list)
    for k, pid in keys:
        by_first[tokens[k][0]].append(k)
    remap = {}
    for first, ks in by_first.items():
        for a in ks:
            ta = tokens[a]
            if len(ta) < 2:
                continue
            cands = [b for b in ks if b != a and len(tokens[b]) > len(ta) and set(ta) <= set(tokens[b])
                     and tokens[b][-1] == ta[-1] or (b != a and len(tokens[b]) > len(ta) and set(ta) <= set(tokens[b]) and
                                                     " ".join(tokens[b]).startswith(" ".join(ta)))]
            cands = list(dict.fromkeys(cands))
            if len(cands) == 1:
                remap[P.by_key[a]] = P.by_key[cands[0]]
    # follow chains
    def final(p):
        seen = set()
        while p in remap and p not in seen:
            seen.add(p)
            p = remap[p]
        return p
    for src in list(remap):
        dst = final(src)
        if src == dst or src not in P.people or dst not in P.people:
            continue
        a, b = P.people[src], P.people[dst]
        b["names"].update(a["names"])
        b["bios"] += a["bios"]
        b["appearances"] += a["appearances"]
        b["web_slugs"] |= a["web_slugs"]
        b["affiliations"].update(a["affiliations"])
        b["photo"] = b["photo"] or a["photo"]
        del P.people[src]
        for k, v in list(P.by_key.items()):
            if v == src:
                P.by_key[k] = dst
        for r in refs:
            for pr in r:
                if pr["person"] == src:
                    pr["person"] = dst
    return len(remap)


def main():
    web = json.load(open(DATA / "web.json"))
    cats = {}
    for y in YEARS:
        p = DATA / "catalogues" / f"{y}.json"
        if p.exists():
            cats[y] = json.load(open(p))
    P = People()

    # ---------- films ----------
    films = {}
    film_by_key = {}

    def film_for(title, year):
        k = title_key(title)
        if k in film_by_key and (year is None or any(abs(year - y) <= 1 for y in films[film_by_key[k]]["years"]) or not films[film_by_key[k]]["years"]):
            return film_by_key[k]
        k2 = title_key(re.sub(r"\s*\(.*?\)\s*$", "", title or ""))
        if k2 != k and k2 in film_by_key:
            return film_by_key[k2]
        for kk, fid in list(film_by_key.items()):
            if title_key(re.sub(r"\s*\(.*?\)\s*$", "", films[fid]["title"])) == k and year in films[fid]["years"]:
                return fid
        # fuzzy: same festival year, close title
        for kk, fid in film_by_key.items():
            if year in films[fid]["years"] and difflib.SequenceMatcher(None, k, kk).ratio() > 0.9:
                return fid
        tl = (title or "").lower()
        for kk, fid in film_by_key.items():
            ot = films[fid]["title"].lower()
            if year in films[fid]["years"] and len(kk) > 6 and len(k) > 6 and (
                    tl.startswith(ot + ":") or ot.startswith(tl + ":") or kk.startswith(k + " ") and ":" in ot or k.startswith(kk + " ") and ":" in tl):
                return fid
        fid = slugify(title)
        if fid in films:
            fid = f"{fid}-{year}"
        films[fid] = {"id": fid, "title": title, "years": [], "directors": [], "country": None, "film_year": None,
                      "runtime_min": None, "synopsis": None, "is_short": None, "screenings": [], "people": [],
                      "image": None, "dxfest_url": None, "sources": []}
        if k not in film_by_key:
            film_by_key[k] = fid
        return fid

    for y, c in sorted(cats.items()):
        for f in c.get("films", []):
            if not f.get("title"):
                continue
            fid = film_for(f["title"], y)
            F = films[fid]
            if y not in F["years"]:
                F["years"].append(y)
            for k in ("country", "film_year", "runtime_min"):
                F[k] = F[k] or f.get(k)
            if f.get("synopsis") and len(f["synopsis"]) > len(F["synopsis"] or ""):
                F["synopsis"] = f["synopsis"]
            if F["is_short"] is None:
                F["is_short"] = f.get("is_short")
            sc = f.get("screening") or {}
            F["screenings"].append({"year": y, "date": sc.get("date"), "time": sc.get("time"), "venue": sc.get("venue"),
                                    "slot": f.get("slot"), "premiere": f.get("premiere"), "shorts_program": f.get("shorts_program"),
                                    "after": f.get("after_screening"), "page": f.get("page")})
            F["sources"].append({"kind": "catalogue", "year": y, "page": f.get("page")})
            for d in f.get("directors") or []:
                pid = P.resolve(d)
                if pid:
                    P.add_name(pid, d)
                    F["people"].append({"person": pid, "role": "director", "year": y})
            for pr in f.get("people") or []:
                pid = P.resolve(pr.get("name"))
                if pid:
                    P.add_name(pid, pr["name"])
                    role = (pr.get("role") or "guest").lower()
                    if role == "director" and any(x["person"] == pid and x["role"] == "director" for x in F["people"]):
                        continue
                    F["people"].append({"person": pid, "role": role, "year": y})

    SLOT = {"opening": "Opening Night", "closing": "Closing Night", "centerpiece": "Centerpiece", "spotlight": "Spotlight"}
    for w in web["films"]:
        if not w["festival_years"]:
            continue  # redirected to the ticketing site, or a year-round event page
        ys = w["festival_years"]
        y = ys[0] if ys else None
        if re.match(r"^short(s)?\s*(cuts|program)", w["title"], re.I) and y in cats:
            continue
        fid = film_for(w["title"], y)
        F = films[fid]
        F["dxfest_url"] = w["url"]
        F["image"] = F["image"] or w.get("image")
        for k in ("country", "film_year", "runtime_min"):
            F[k] = F[k] or w.get(k)
        if not F["synopsis"] or (len(w["synopsis"]) > 1.3 * len(F["synopsis"] or "")):
            F["synopsis"] = F["synopsis"] or w["synopsis"]
        for yy in ys:
            if yy not in F["years"]:
                F["years"].append(yy)
                slot = next((SLOT[f] for f in w["slot_flags"] if f in SLOT), None)
                F["screenings"].append({"year": yy, "slot": slot})
        if not any(p["role"] == "director" for p in F["people"]):
            for d in split_names(w.get("director_line")):
                pid = P.resolve(d)
                if pid:
                    P.add_name(pid, d)
                    F["people"].append({"person": pid, "role": "director", "year": y})
        F["sources"].append({"kind": "website", "url": w["url"]})
    for F in films.values():
        F["years"].sort()
        if F["is_short"] is None:
            F["is_short"] = bool(F["runtime_min"] and F["runtime_min"] < 45)
        names = [P.people[p["person"]]["name"] for p in F["people"] if p["role"] == "director"]
        F["directors"] = list(dict.fromkeys(p["person"] for p in F["people"] if p["role"] == "director"))
        F["topics"] = topics_for(" ".join([F["title"], F["synopsis"] or ""]))

    # ---------- sessions ----------
    sessions = {}
    sess_by_key = {}

    def session_for(title, year, date=None):
        k = (year, title_key(title))
        if k in sess_by_key:
            return sess_by_key[k], False
        for (yy, kk), sid in sess_by_key.items():
            if yy == year and kk and difflib.SequenceMatcher(None, k[1], kk).ratio() > 0.86:
                return sid, False
        if title.isupper() and len(title.split()) >= 3:
            small = {"a", "an", "the", "of", "and", "in", "on", "for", "to", "at", "by", "with", "&"}
            title = " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(title.lower().split()))
        sid = f"{year}-{slugify(title)[:70]}"
        base, n = sid, 2
        while sid in sessions:
            sid = f"{base}-{n}"
            n += 1
        sessions[sid] = {"id": sid, "title": title, "year": year, "kind": None, "date": date, "time": None, "end_time": None,
                         "venue": None, "description": None, "people": [], "related_films": [], "videos": [],
                         "dxfest_url": None, "sources": [], "track": None}
        sess_by_key[k] = sid
        return sid, True

    for y, c in sorted(cats.items()):
        for s in c.get("sessions", []):
            t = (s.get("title") or "").strip()
            if not t or NOT_SESSIONS.match(t):
                continue
            sid, _ = session_for(t, y, s.get("date"))
            S = sessions[sid]
            for k in ("kind", "date", "time", "end_time", "venue"):
                S[k] = S[k] or s.get(k)
            if s.get("description") and len(s["description"]) > len(S["description"] or ""):
                S["description"] = s["description"]
            S["sources"].append({"kind": "catalogue", "year": y, "page": s.get("page")})
            S["page"] = S.get("page") or s.get("page")
            for rf in s.get("related_films") or []:
                if rf:
                    S["related_films"].append(rf)
            for pr in s.get("people") or []:
                pid = P.resolve(pr.get("name"))
                if pid:
                    P.add_name(pid, pr["name"])
                    S["people"].append({"person": pid, "role": (pr.get("role") or "speaker").lower()})

    speakers_by_slug = {s["slug"]: s for s in web["speakers"]}
    for w in web["sessions"]:
        y = w.get("year")
        t = (w.get("title") or "").strip()
        if not y or not t or NOT_SESSIONS.match(t):
            continue
        ft = re.sub(r"^(?:(?:opening night|closing night|centerpiece|spotlight)\s*)?(?:film\s*)?(?:screening)?\s*:\s*", "", t, flags=re.I)
        ft = re.sub(r"\s+library screening$", "", ft, flags=re.I)
        fk = title_key(ft)
        fmatch = film_by_key.get(fk) or next((fid for kk, fid in film_by_key.items() if y in films[fid]["years"] and (
            difflib.SequenceMatcher(None, fk, kk).ratio() > 0.88 or (len(fk) > 6 and kk.startswith(fk + " ")))), None)
        if (ft != t or "film-screening" in w["kinds"]) and fmatch:
            # a screening page: attach its speakers to the film instead
            F = films[fmatch]
            if y not in F["years"]:
                F["years"].append(y)
                F["screenings"].append({"year": y, "slot": None, "note": t})
            if not F.get("dxfest_url"):
                F["dxfest_url"] = w["url"]
            for sl in w.get("speaker_slugs", []):
                sp = speakers_by_slug.get(sl)
                pid = sp and P.resolve(sp["name"])
                if pid:
                    P.people[pid]["web_slugs"].add(sl)
                    if not any(x["person"] == pid for x in F["people"]):
                        F["people"].append({"person": pid, "role": "guest", "year": y})
            continue
        sid, new = session_for(t, y, w.get("date"))
        S = sessions[sid]
        S["dxfest_url"] = w["url"]
        for k in ("date", "time", "end_time", "venue"):
            S[k] = S[k] or w.get(k)
        if w.get("description") and len(w["description"]) > len(S["description"] or ""):
            S["description"] = w["description"]
        S["videos"] = sorted(set(S["videos"]) | set(w.get("videos") or []))
        if "dx-squared" in w["kinds"]:
            S["track"] = "DX²"
        if not S["kind"]:
            S["kind"] = "workshop" if "workshop" in w["kinds"] else ("screening-event" if "film-screening" in w["kinds"] else "panel")
        S["sources"].append({"kind": "website", "url": w["url"]})
        have = {x["person"] for x in S["people"]}
        for sl in w.get("speaker_slugs", []):
            sp = speakers_by_slug.get(sl)
            pid = sp and P.resolve(sp["name"])
            if pid:
                P.people[pid]["web_slugs"].add(sl)
                if pid not in have:
                    S["people"].append({"person": pid, "role": "speaker"})
                    have.add(pid)

    # link sessions <-> films
    for S in sessions.values():
        linked = []
        for rf in S["related_films"]:
            fid = film_by_key.get(title_key(rf))
            if fid and fid not in linked:
                linked.append(fid)
        text = " ".join([S["title"], S["description"] or ""])
        for k, fid in film_by_key.items():
            F = films[fid]
            if S["year"] in F["years"] and len(F["title"]) > 5 and fid not in linked:
                if re.search(r"\b" + re.escape(F["title"]) + r"\b", text, re.I):
                    linked.append(fid)
        S["films"] = linked
        S["topics"] = topics_for(text)

    # ---------- bios, organisers, awards ----------
    for y, c in sorted(cats.items()):
        for pr in c.get("people", []):
            pid = P.resolve(pr.get("name"))
            if pid:
                P.add_name(pid, pr["name"])
                if pr.get("bio"):
                    P.people[pid]["bios"].append({"year": y, "source": "catalogue", "page": pr.get("page"), "text": pr["bio"]})
                if pr.get("affiliation"):
                    P.people[pid]["affiliations"][pr["affiliation"]] += 1
        for o in c.get("organizers", []):
            pid = P.resolve(o.get("name"))
            if pid:
                P.add_name(pid, o["name"])
                P.people[pid]["appearances"].append({"type": "team", "year": y, "role": o.get("role") or "Festival team"})
        for a in c.get("awards", []):
            for nm in split_names(a.get("recipient")):
                pid = P.resolve(nm)
                if pid:
                    P.people[pid]["appearances"].append({"type": "award", "year": y, "role": "honoree",
                                                         "label": a.get("name"), "film": a.get("film")})

    CAT_LABEL = [(r"dx-access", "DX Access"), (r"dx-academy", "DX Academy"), (r"dx-pitch", "DX Pitch"),
                 (r"dx-legal", "DX Legal"), (r"contributors", "Contributor"), (r"crossing-borders", "Crossing Borders")]
    for sp in web["speakers"]:
        pid = P.resolve(sp["name"])
        if not pid:
            continue
        Pp = P.people[pid]
        P.add_name(pid, sp["name"])
        Pp["web_slugs"].add(sp["slug"])
        Pp["photo"] = Pp["photo"] or sp.get("photo")
        Pp.setdefault("dxfest_urls", []).append(sp["url"])
        if sp.get("bio"):
            yb = max(sp["years"]) if sp["years"] else int(sp["created"][:4])
            Pp["bios"].append({"year": yb, "source": "website", "url": sp["url"], "text": sp["bio"]})
        for cat in sp["categories"]:
            for rx, lab in CAT_LABEL:
                if re.search(rx, cat):
                    ys = re.findall(r"20\d\d", cat)
                    Pp["appearances"].append({"type": "program", "year": int(ys[0]) if ys else None, "role": lab})
        Pp.setdefault("listed_years", set()).update(sp["years"])

    # appearances from films and sessions
    for F in films.values():
        for pr in F["people"]:
            P.people[pr["person"]]["appearances"].append({"type": "film", "id": F["id"], "year": pr.get("year") or (F["years"][0] if F["years"] else None), "role": pr["role"]})
    for S in sessions.values():
        for pr in S["people"]:
            P.people[pr["person"]]["appearances"].append({"type": "session", "id": S["id"], "year": S["year"], "role": pr["role"]})

    merged = merge_similar_people(P, [F["people"] for F in films.values()] + [S["people"] for S in sessions.values()])
    for F in films.values():
        F["directors"] = list(dict.fromkeys(p["person"] for p in F["people"] if p["role"] == "director"))

    # finalise people
    people = {}
    for pid, Pp in P.people.items():
        apps = []
        seen = set()
        for a in Pp["appearances"]:
            key = (a["type"], a.get("id"), a.get("year"), a.get("role"))
            if key in seen:
                continue
            seen.add(key)
            apps.append(a)
        years = sorted({a["year"] for a in apps if a.get("year")} | {b["year"] for b in Pp["bios"] if b.get("source") == "catalogue"}
                       | set(Pp.get("listed_years") or []))
        if not apps and not Pp["bios"]:
            continue
        groups = Counter()
        for a in apps:
            groups["team" if a["type"] == "team" else role_group(a["role"]) if a["type"] != "program" else "speaker"] += 1
        name = Pp["names"].most_common(1)[0][0] if Pp["names"] else Pp["name"]
        # prefer the longest common variant ("Ramona S. Diaz" over "Ramona Diaz") only if it appears in a bio
        bios = sorted(Pp["bios"], key=lambda b: (b.get("year") or 0, b["source"] == "website"), reverse=True)
        uniq_bios = []
        for b in bios:
            if not any(difflib.SequenceMatcher(None, b["text"][:300], u["text"][:300]).ratio() > 0.8 for u in uniq_bios):
                uniq_bios.append(b)
        biotext = " ".join(b["text"] for b in uniq_bios)
        topics = Counter()
        for a in apps:
            if a["type"] == "film" and a["id"] in films:
                topics.update(films[a["id"]]["topics"])
            elif a["type"] == "session" and a["id"] in sessions:
                topics.update(sessions[a["id"]]["topics"])
        people[pid] = {
            "id": pid, "name": Pp["name"] if Pp["name"] in Pp["names"] else name,
            "variants": sorted(n for n in Pp["names"] if n != Pp["name"]),
            "bios": uniq_bios, "photo": Pp["photo"], "appearances": apps, "years": years,
            "groups": [g for g, _ in groups.most_common()],
            "affiliation": Pp["affiliations"].most_common(1)[0][0] if Pp["affiliations"] else None,
            "orgs": orgs_for(biotext), "topics": [t for t, _ in topics.most_common()],
            "dxfest_urls": sorted(set(Pp.get("dxfest_urls") or [])),
        }

    # collaborators
    for coll in [F["people"] for F in films.values()] + [S["people"] for S in sessions.values()]:
        ids = list(dict.fromkeys(p["person"] for p in coll if p["person"] in people))
        for a in ids:
            c = people[a].setdefault("_co", Counter())
            for b in ids:
                if a != b:
                    c[b] += 1
    for p in people.values():
        p["collaborators"] = [b for b, _ in p.pop("_co", Counter()).most_common(24)]

    # editions
    editions = {}
    for y in YEARS:
        c = cats.get(y, {})
        e = {"year": y, "number": y - 2014, "dates": c.get("dates"), "theme": c.get("theme"),
             "edition_name": c.get("edition_name"), "venues": c.get("venues") or [], "format": "In person",
             "catalogue": CATALOGUE_PDF.get(y),
             "catalogue_wayback": (f"https://web.archive.org/web/{CATALOGUE_TS[y]}/{CATALOGUE_PDF[y]}" if y in CATALOGUE_PDF else None),
             "awards": c.get("awards") or [], "note": None}
        for k, v in EDITION_FACTS.get(y, {}).items():
            e[k] = e.get(k) or v
        e["films"] = sorted([f["id"] for f in films.values() if y in f["years"]], key=lambda i: films[i]["title"].lower())
        e["sessions"] = sorted([s["id"] for s in sessions.values() if s["year"] == y],
                               key=lambda i: (sessions[i]["date"] or "9", sessions[i]["time"] or "", sessions[i]["title"]))
        e["people"] = sorted([p["id"] for p in people.values() if y in p["years"]], key=lambda i: people[i]["name"].split()[-1].lower())
        editions[y] = e

    # venues
    venues = defaultdict(lambda: {"years": set(), "films": [], "sessions": []})
    for F in films.values():
        for s in F["screenings"]:
            if venue_canon(s.get("venue")):
                v = venues[venue_canon(s["venue"])]
                v["years"].add(s["year"])
                v["films"].append(F["id"])
    for S in sessions.values():
        if venue_canon(S.get("venue")):
            v = venues[venue_canon(S["venue"])]
            v["years"].add(S["year"])
            v["sessions"].append(S["id"])
    venues = {slugify(k): {"id": slugify(k), "name": k, "years": sorted(v["years"]), "films": sorted(set(v["films"])),
                           "sessions": sorted(set(v["sessions"]))} for k, v in venues.items()}

    out = {
        "editions": editions, "films": films, "sessions": sessions, "people": people, "venues": venues,
        "topics": {k: {"id": k, "label": v[0], "blurb": v[1]} for k, v in TOPICS.items()},
        "orgs": {s: {"id": s, "label": l, "kind": k} for s, l, k, _ in ORG_RX},
    }
    json.dump(out, open(DATA / "festival.json", "w"), indent=1, ensure_ascii=False, default=sorted)
    print(f"films {len(films)}  sessions {len(sessions)}  people {len(people)}  venues {len(venues)}  merged-names {merged}")
    for y in YEARS:
        e = editions[y]
        print(y, "films", len(e["films"]), "sessions", len(e["sessions"]), "people", len(e["people"]))


if __name__ == "__main__":
    main()
