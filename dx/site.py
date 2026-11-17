"""Build the static site into public/ from data/festival.json.

    python3 -m dx.site
"""
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path

from .model import CATALOGUE_PDF, CATALOGUE_TS, ROLE_GROUP_LABEL, YEARS, slugify
from .topics import ORG_KIND_LABEL

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
STATIC = Path(__file__).resolve().parent / "static"
TITLE = "Double Exposure Explorer"
BASE_URL = "https://wayback-labs.sf.archive.org/dxfest/"
V = "3"

KIND_LABEL = {"panel": "Panel", "keynote": "Keynote", "workshop": "Workshop", "masterclass": "Masterclass",
              "conversation": "Conversation", "pitch": "Pitch", "award": "Awards", "screening-event": "Screening event",
              "reception": "Reception", "other": "Event", None: "Session"}
KIND_PLURAL = {"panel": "Panels", "keynote": "Keynotes", "workshop": "Workshops", "masterclass": "Masterclasses",
               "conversation": "Conversations", "pitch": "Pitches", "award": "Awards", "screening-event": "Screening events",
               "reception": "Receptions & parties", "other": "Other events"}
GROUP_ORDER = ["filmmaker", "moderator", "speaker", "keynote", "trainer", "journalist", "subject", "juror", "honoree",
               "fellow", "pitch", "team"]
GROUP_BLURB = {
    "filmmaker": "Directors, producers and crew of films that screened.",
    "moderator": "People who moderated panels and post-screening conversations.",
    "speaker": "Panelists, presenters and guests at forum sessions and screenings.",
    "keynote": "Keynote speakers.",
    "trainer": "People who led workshops, masterclasses and trainings.",
    "journalist": "Reporters whose investigations the films drew on, credited as such.",
    "subject": "People the films are about who came to the festival.",
    "juror": "Members of award juries.",
    "honoree": "Award recipients and honorees.",
    "fellow": "Fellows of the festival's programmes.",
    "pitch": "Filmmakers who pitched projects.",
    "team": "Festival staff, programmers, board and advisers named in the catalogues.",
}


def plural(n, w, ws=None):
    return f"{n:,} {w if n == 1 else (ws or w + 's')}"


def nice_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except Exception:
        return d or ""


def short_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d")
    except Exception:
        return d or ""


def paras(t):
    if not t:
        return ""
    return "".join(f"<p>{escape(p.strip())}</p>" for p in re.split(r"\n\s*\n", t) if p.strip())


def excerpt(t, n=220):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:—-") + "…"


def wayback(url):
    return f"https://web.archive.org/web/2026/{url}"


class Site:
    def __init__(self):
        d = json.load(open(DATA / "festival.json"))
        self.E = {int(k): v for k, v in d["editions"].items()}
        self.F = d["films"]
        self.S = d["sessions"]
        self.P = d["people"]
        self.V = d["venues"]
        self.T = d["topics"]
        self.O = d["orgs"]
        self.img = json.load(open(DATA / "images.json")) if (DATA / "images.json").exists() else {}
        self.urls = []
        # derived indexes
        self.topic_films = defaultdict(list)
        self.topic_sessions = defaultdict(list)
        self.topic_people = defaultdict(list)
        for f in self.F.values():
            for t in f["topics"]:
                self.topic_films[t].append(f["id"])
        for s in self.S.values():
            for t in s["topics"]:
                self.topic_sessions[t].append(s["id"])
        for p in self.P.values():
            for t in p["topics"][:6]:
                self.topic_people[t].append(p["id"])
        self.org_people = defaultdict(list)
        for p in self.P.values():
            for o in p["orgs"]:
                self.org_people[o].append(p["id"])
        self.group_people = defaultdict(list)
        for p in self.P.values():
            for g in p["groups"]:
                self.group_people[g].append(p["id"])
        self.film_sessions = defaultdict(list)
        for s in self.S.values():
            for fid in s.get("films", []):
                self.film_sessions[fid].append(s["id"])
        self.countries = defaultdict(list)
        for f in self.F.values():
            for c in self.split_countries(f.get("country")):
                self.countries[c].append(f["id"])

    @staticmethod
    def split_countries(c):
        if not c:
            return []
        out = []
        for x in re.split(r",|/|;|\band\b|&", c):
            x = x.strip().strip(".")
            x = {"USA": "United States", "US": "United States", "U.S.": "United States", "U.S": "United States",
                 "United States of America": "United States", "UK": "United Kingdom", "U.K.": "United Kingdom",
                 "England": "United Kingdom"}.get(x, x)
            if x and len(x) < 40:
                out.append(x)
        return out

    # ---------- shell ----------
    def page(self, path, title, body, desc="", crumbs=None, active=""):
        depth = path.count("/")
        rel = "../" * depth
        nav = [("index.html", "Home", "home"), ("years.html", "Years", "years"), ("people.html", "People", "people"),
               ("films.html", "Films", "films"), ("sessions.html", "Sessions", "sessions"),
               ("topics.html", "Topics", "topics"), ("orgs.html", "Organisations", "orgs"), ("search.html", "Search", "search")]
        navh = "".join(f'<a href="{rel}{h}"{" aria-current=\"page\"" if a == active else ""}>{l}</a>' for h, l, a in nav)
        crumb = ""
        if crumbs:
            crumb = '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(
                f'<a href="{rel}{h}">{escape(l)}</a>' if h else escape(l) for h, l in crumbs) + "</nav>"
        full = f"{title} · {TITLE}" if title != TITLE else TITLE
        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(full)}</title>
<meta name="description" content="{escape(desc or 'Twelve years of the Double Exposure Investigative Film Festival: every film, session and person, 2015–2026.')}">
<link rel="canonical" href="{BASE_URL}{path}">
<link rel="icon" href="{rel}img/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{rel}style.css?v={V}">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
<a class="brand" href="{rel}index.html"><span class="mark" aria-hidden="true">DX</span><span class="bt">Double Exposure <em>Explorer</em></span></a>
<nav class="main" aria-label="Main">{navh}</nav>
</div></header>
<main id="main" class="wrap">
{crumb}
{body}
</main>
<footer><div class="wrap foot">
<div class="foot-l"><a href="https://archive.org/"><img src="{rel}img/internet-archive.png" alt="Internet Archive" width="40" height="40"></a>
<p>A Wayback Machine Labs experiment, Internet Archive.<br>
Feedback? <a href="mailto:info@archive.org?subject=Double%20Exposure%20Explorer">Email us</a></p></div>
<p class="foot-r">An independent index of the <a href="https://dxfest.com/">Double Exposure Investigative Film Festival</a>, built from its catalogues and website.<br><a href="{rel}about.html">About this site</a> · <a href="{rel}about.html#accessibility">Accessibility</a></p>
</div></footer>
<script src="{rel}app.js?v={V}" defer></script>
</body></html>
"""
        out = PUBLIC / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        self.urls.append(path)

    # ---------- small renderers ----------
    def plink(self, pid, rel, cls=""):
        p = self.P[pid]
        return f'<a class="{cls}" href="{rel}people/{pid}.html">{escape(p["name"])}</a>' if cls else f'<a href="{rel}people/{pid}.html">{escape(p["name"])}</a>'

    def flink(self, fid, rel):
        return f'<a href="{rel}films/{fid}.html"><cite>{escape(self.F[fid]["title"])}</cite></a>'

    def slink(self, sid, rel):
        return f'<a href="{rel}sessions/{sid}.html">{escape(self.S[sid]["title"])}</a>'

    def tchips(self, topics, rel, n=99):
        return "".join(f'<a class="chip t" href="{rel}topics/{t}.html">{escape(self.T[t]["label"])}</a>' for t in topics[:n] if t in self.T)

    def photo(self, pid, rel, size="s"):
        im = self.img.get("p:" + pid)
        p = self.P[pid]
        if im:
            return f'<img class="ph {size}" src="{rel}{im}" alt="" loading="lazy" width="96" height="96">'
        ini = "".join(w[0] for w in p["name"].split()[:2] if w[:1].isalpha()).upper()
        return f'<span class="ph {size} ini" aria-hidden="true">{escape(ini)}</span>'

    def still(self, fid, rel):
        im = self.img.get("f:" + fid)
        if im:
            return f'<img class="still" src="{rel}{im}" alt="" loading="lazy" width="480" height="256">'
        f = self.F[fid]
        return f'<span class="still blank" aria-hidden="true">{escape(f["title"][:1])}</span>'

    def person_role_line(self, pid):
        p = self.P[pid]
        bits = [ROLE_GROUP_LABEL.get(g, g).rstrip("s").replace("Panelists & speaker", "Panelist").lower() for g in p["groups"][:3]]
        yrs = p["years"]
        span = f"{yrs[0]}" if len(yrs) == 1 else (f"{len(yrs)} editions, {yrs[0]}–{yrs[-1]}" if yrs else "")
        return " · ".join([b for b in [", ".join(bits).capitalize(), span] if b])

    def pcard(self, pid, rel, extra=""):
        p = self.P[pid]
        aff = p.get("affiliation") or ""
        return (f'<li class="pc">{self.photo(pid, rel)}<div><a href="{rel}people/{pid}.html">{escape(p["name"])}</a>'
                f'<span class="sub">{escape(extra or self.person_role_line(pid))}</span>'
                f'{f"<span class=sub2>{escape(aff)}</span>" if aff and not extra else ""}</div></li>')

    def fcard(self, fid, rel, note=""):
        f = self.F[fid]
        dirs = ", ".join(self.P[d]["name"] for d in f["directors"][:3] if d in self.P)
        meta = " · ".join(str(x) for x in [", ".join(str(y) for y in f["years"]), f"{f['runtime_min']} min" if f.get("runtime_min") else None] if x)
        return (f'<li class="fc" data-years="{" ".join(map(str, f["years"]))}" data-topics="{" ".join(f["topics"])}" data-short="{1 if f.get("is_short") else 0}">'
                f'<a href="{rel}films/{fid}.html">{self.still(fid, rel)}<span class="ft">{escape(f["title"])}</span></a>'
                f'<span class="sub">{escape(dirs)}</span><span class="sub2">{escape(note or meta)}</span></li>')

    def srow(self, sid, rel, show_year=True):
        s = self.S[sid]
        who = [self.P[x["person"]]["name"] for x in s["people"] if x["person"] in self.P]
        when = " · ".join(x for x in [str(s["year"]) if show_year else None, short_date(s.get("date")) if s.get("date") else None,
                                      s.get("time")] if x)
        return (f'<li class="sr" data-kind="{escape(s.get("kind") or "")}" data-topics="{" ".join(s["topics"])}">'
                f'<span class="when">{escape(when)}</span><span class="kind">{escape(KIND_LABEL.get(s.get("kind"), "Session"))}{" · DX²" if s.get("track") else ""}</span>'
                f'<a href="{rel}sessions/{sid}.html">{escape(s["title"])}</a>'
                f'{f"<span class=sub>{escape(excerpt(", ".join(who), 140))}</span>" if who else ""}</li>')

    def years_strip(self, years, rel):
        cells = []
        for y in YEARS:
            on = y in years
            cells.append(f'<a class="yc{" on" if on else ""}" href="{rel}years/{y}.html" title="{y}{": appeared" if on else ""}">{str(y)[2:]}</a>')
        return '<div class="ystrip" aria-label="Editions">' + "".join(cells) + "</div>"

    def cat_link(self, year, page, label=None):
        if year not in CATALOGUE_PDF or not page:
            return ""
        u = f"https://web.archive.org/web/{CATALOGUE_TS[year]}id_/{CATALOGUE_PDF[year]}#page={page}"
        return f'<a href="{u}">{escape(label or f"{year} catalogue, p. {page}")}</a>'

    # ---------- pages ----------
    def build(self):
        if PUBLIC.exists():
            for p in PUBLIC.iterdir():
                if p.name == "img":
                    continue
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        PUBLIC.mkdir(exist_ok=True)
        (PUBLIC / "img").mkdir(exist_ok=True)
        for f in STATIC.iterdir():
            if f.is_file():
                shutil.copy(f, PUBLIC / f.name)
        for f in (STATIC / "img").iterdir():
            shutil.copy(f, PUBLIC / "img" / f.name)
        self.home()
        self.years_index()
        for y in YEARS:
            self.year_page(y)
        self.people_index()
        for g in GROUP_ORDER:
            if self.group_people.get(g):
                self.role_page(g)
        self.regulars()
        for pid in self.P:
            self.person_page(pid)
        self.films_index()
        for fid in self.F:
            self.film_page(fid)
        self.countries_page()
        self.sessions_index()
        for sid in self.S:
            self.session_page(sid)
        self.topics_index()
        for t in self.T:
            self.topic_page(t)
        self.orgs_index()
        for o in self.O:
            if self.org_people.get(o):
                self.org_page(o)
        self.venues_index()
        for v in self.V:
            self.venue_page(v)
        self.search_page()
        self.about()
        self.notfound()
        self.search_index()
        self.sitemap()
        print(f"{len(self.urls)} pages")

    def counts(self):
        return len(self.F), len(self.S), len(self.P)

    def home(self):
        nf, ns, np_ = self.counts()
        cards = []
        for y in YEARS:
            e = self.E[y]
            tc = Counter(t for f in e["films"] for t in self.F[f]["topics"])
            tops = ", ".join(self.T[t]["label"] for t, _ in tc.most_common(2))
            cards.append(f'<li class="ed"><a href="years/{y}.html"><span class="yr">{y}</span>'
                         f'<span class="ord">{ordinal(e["number"])} edition{" · " + escape(e["format"]) if e.get("format") and e["format"] != "In person" else ""}</span>'
                         f'<span class="dt">{escape(e.get("dates") or "")}</span>'
                         f'<span class="ct">{plural(len(e["films"]), "film")} · {plural(len(e["sessions"]), "session")} · {plural(len(e["people"]), "person", "people")}</span>'
                         f'{f"<span class=tp>{escape(tops)}</span>" if tops else ""}</a></li>')
        regulars = sorted(self.P.values(), key=lambda p: (-len(p["years"]), -len(p["appearances"]), p["name"]))
        regulars = [p for p in regulars if not p["groups"] == ["team"]][:12]
        tcount = {t: len(self.topic_films[t]) + len(self.topic_sessions[t]) for t in self.T}
        mx = max(tcount.values()) or 1
        cloud = "".join(f'<a class="tw" style="--w:{0.85 + 0.9 * (tcount[t] / mx):.2f}" href="topics/{t}.html">{escape(self.T[t]["label"])}<span>{tcount[t]}</span></a>'
                        for t in sorted(self.T, key=lambda t: self.T[t]["label"]) if tcount[t])
        groups = "".join(f'<a class="chip g" href="roles/{g}.html">{escape(ROLE_GROUP_LABEL[g])} <span>{len(self.group_people[g])}</span></a>'
                         for g in GROUP_ORDER if self.group_people.get(g))
        ftile = [fid for fid in sorted(self.F, key=lambda i: (-max(self.F[i]["years"] or [0]), self.F[i]["title"])) if self.img.get("f:" + fid)]
        picks = []
        seen_y = Counter()
        for fid in ftile:
            y = max(self.F[fid]["years"])
            if seen_y[y] < 1:
                picks.append(fid)
                seen_y[y] += 1
        body = f"""
<section class="hero">
<h1>Twelve years of investigative film</h1>
<p class="lede">The <strong>Double Exposure Investigative Film Festival</strong> has brought filmmakers and investigative journalists together in Washington, DC every year since 2015. This explorer gathers its {plural(nf, "film")}, {plural(ns, "forum session")} and {plural(np_, "person", "people")} from the festival’s twelve editions, so you can follow a filmmaker, a reporter or a subject across the years.</p>
<form class="bigsearch" action="search.html" method="get" role="search"><label for="q" class="vh">Search people, films and sessions</label>
<input id="q" name="q" type="search" placeholder="Search a name, a film, a topic…" autocomplete="off"><button type="submit">Search</button></form>
<div class="stats"><a href="films.html"><b>{nf}</b> films</a><a href="sessions.html"><b>{ns}</b> sessions</a><a href="people.html"><b>{np_:,}</b> people</a><a href="years.html"><b>12</b> editions</a><a href="topics.html"><b>{len(self.T)}</b> topics</a><a href="orgs.html"><b>{sum(1 for o in self.O if self.org_people.get(o))}</b> organisations</a></div>
</section>
<section><h2>The editions</h2><ol class="eds">{''.join(cards)}</ol></section>
<section class="two">
<div><h2>Who took part</h2><p class="note">Browse people by what they did at the festival.</p><div class="chips">{groups}</div>
<h3>Regulars</h3><p class="note">People who came back the most. <a href="regulars.html">All regulars →</a></p><ul class="plist">{''.join(self.pcard(p["id"], "") for p in regulars)}</ul></div>
<div><h2>Topics</h2><p class="note">Films and sessions grouped by subject. Size shows how often each topic comes up.</p><div class="cloud">{cloud}</div></div>
</section>
<section><h2>A film from each year</h2><ul class="fgrid">{''.join(self.fcard(f, "") for f in picks)}</ul><p><a href="films.html">All {nf} films →</a></p></section>
"""
        self.page("index.html", TITLE, body, active="home")

    def years_index(self):
        rows = []
        for y in YEARS:
            e = self.E[y]
            cat = f'<a href="{e["catalogue_wayback"]}">Catalogue (Wayback Machine)</a>' if e.get("catalogue_wayback") else "No catalogue"
            rows.append(f'<tr><th scope="row"><a href="years/{y}.html">{y}</a></th><td>{ordinal(e["number"])}</td><td>{escape(e.get("dates") or "")}</td>'
                        f'<td>{escape(e.get("format") or "")}</td><td class="n">{len(e["films"])}</td><td class="n">{len(e["sessions"])}</td><td class="n">{len(e["people"])}</td><td>{cat}</td></tr>')
        body = f"""<h1>The editions, 2015–2026</h1>
<p class="lede">Double Exposure has run every year since 2015. The 2020 and 2021 editions were held online.</p>
<div class="tablewrap"><table class="t"><thead><tr><th>Year</th><th>Edition</th><th>Dates</th><th>Format</th><th class="n">Films</th><th class="n">Sessions</th><th class="n">People</th><th>Programme</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""
        self.page("years.html", "Editions", body, crumbs=[("index.html", "Home"), (None, "Editions")], active="years")

    def year_page(self, y):
        rel = "../"
        e = self.E[y]
        prev_ = f'<a href="{y-1}.html">← {y-1}</a>' if y > YEARS[0] else "<span></span>"
        next_ = f'<a href="{y+1}.html">{y+1} →</a>' if y < YEARS[-1] else "<span></span>"
        films = e["films"]
        feat = [f for f in films if not self.F[f].get("is_short")]
        shorts = [f for f in films if self.F[f].get("is_short")]

        def slot(fid):
            for s in self.F[fid]["screenings"]:
                if s["year"] == y and s.get("slot"):
                    return s["slot"]
            return ""
        order = {"Opening Night": 0, "Centerpiece": 1, "Spotlight": 2, "Closing Night": 3}
        feat.sort(key=lambda f: (order.get(slot(f), 5), self.F[f]["title"].lower()))
        by_day = defaultdict(list)
        for sid in e["sessions"]:
            by_day[self.S[sid].get("date") or ""].append(sid)
        sched = ""
        for d in sorted(by_day, key=lambda d: d or "9999"):
            items = sorted(by_day[d], key=lambda i: (time_key(self.S[i].get("time")), self.S[i]["title"]))
            sched += f'<h3>{escape(nice_date(d) if d else "Date not listed")}</h3><ul class="slist">{"".join(self.srow(i, rel, False) for i in items)}</ul>'
        groups = defaultdict(list)
        for pid in e["people"]:
            p = self.P[pid]
            gs = set()
            for a in p["appearances"]:
                if a.get("year") == y:
                    gs.add("team" if a["type"] == "team" else ("speaker" if a["type"] == "program" else role_group_of(a["role"])))
            if not gs:
                gs.add("speaker")
            for g in gs:
                groups[g].append(pid)
        ppl = ""
        for g in GROUP_ORDER:
            if groups.get(g):
                ids = sorted(set(groups[g]), key=lambda i: self.P[i]["name"].split()[-1].lower())
                ppl += f'<h3>{escape(ROLE_GROUP_LABEL[g])} <span class="count">{len(ids)}</span></h3><ul class="names">' + "".join(
                    f'<li>{self.plink(i, rel)}</li>' for i in ids) + "</ul>"
        venues = ", ".join(escape(v.get("name") or "") for v in e.get("venues") or [] if v.get("name"))
        tc = Counter(t for f in films for t in self.F[f]["topics"]) + Counter(t for s in e["sessions"] for t in self.S[s]["topics"])
        cat = (f'<p class="src">Programme source: the <a href="{e["catalogue_wayback"]}">{y} festival catalogue</a> (PDF, in the Wayback Machine) and the festival website.</p>'
               if e.get("catalogue_wayback") else
               f'<p class="src">There is no printed catalogue for {y}; this page is built from the festival website{" as the Wayback Machine saved it" if y in (2020, 2021) else ""}.</p>')
        aw = ""
        if e.get("awards"):
            aw = "<section><h2>Awards</h2><ul class='awards'>" + "".join(
                f'<li><b>{escape(a.get("name") or "")}</b>{": " + escape(a.get("recipient") or "") if a.get("recipient") else ""}{" — <cite>" + escape(a["film"]) + "</cite>" if a.get("film") else ""}</li>'
                for a in e["awards"]) + "</ul></section>"
        body = f"""<div class="pager">{prev_}{next_}</div>
<h1>Double Exposure {y}</h1>
<p class="lede">The {ordinal(e["number"])} edition{": " + escape(e["dates"]) if e.get("dates") else ""}{" · " + escape(e["format"]) if e.get("format") else ""}.{(' Theme: “' + escape(e["theme"]) + '”.') if e.get("theme") else ""}</p>
{f'<p class="note">{escape(e["note"])}</p>' if e.get("note") else ""}
{f'<p class="note">Venues: {venues}</p>' if venues else ""}
{cat}
<div class="chips">{self.tchips([t for t, _ in tc.most_common(8)], rel)}</div>
<nav class="jump" aria-label="On this page"><a href="#films">Films ({len(films)})</a><a href="#schedule">Sessions ({len(e["sessions"])})</a><a href="#people">People ({len(e["people"])})</a></nav>
<section id="films"><h2>Films</h2>
<ul class="fgrid">{''.join(self.fcard(f, rel, slot(f)) for f in feat)}</ul>
{f'<h3>Shorts</h3><ul class="fgrid small">{"".join(self.fcard(f, rel) for f in shorts)}</ul>' if shorts else ""}
{'' if films else '<p class="note">No films recorded for this year.</p>'}
</section>
<section id="schedule"><h2>Forum sessions and events</h2>{sched or '<p class="note">No sessions recorded for this year.</p>'}</section>
{aw}
<section id="people"><h2>People</h2>{ppl or '<p class="note">No people recorded.</p>'}</section>
<div class="pager">{prev_}{next_}</div>"""
        self.page(f"years/{y}.html", f"{y}", body, desc=f"Double Exposure {y}: films, sessions and people.",
                  crumbs=[("index.html", "Home"), ("years.html", "Editions"), (None, str(y))], active="years")

    def people_index(self):
        ids = sorted(self.P, key=lambda i: (sortname(self.P[i]["name"])))
        letters = defaultdict(list)
        for i in ids:
            letters[sortname(self.P[i]["name"])[:1].upper() or "#"].append(i)
        az = "".join(f'<a href="#l-{l}">{l}</a>' for l in sorted(letters))
        groups = "".join(f'<a class="chip g" href="roles/{g}.html">{escape(ROLE_GROUP_LABEL[g])} <span>{len(self.group_people[g])}</span></a>'
                         for g in GROUP_ORDER if self.group_people.get(g))
        yrs = "".join(f'<button type="button" class="chip y" data-y="{y}" aria-pressed="false">{y}</button>' for y in YEARS)
        gf = "".join(f'<button type="button" class="chip g" data-g="{g}" aria-pressed="false">{escape(ROLE_GROUP_LABEL[g])}</button>' for g in GROUP_ORDER if self.group_people.get(g))
        blocks = ""
        for l in sorted(letters):
            blocks += f'<h2 id="l-{l}" class="letter">{l}</h2><ul class="plist">' + "".join(
                self.pcard(i, "").replace('<li class="pc">', f'<li class="pc" data-y="{" ".join(map(str, self.P[i]["years"]))}" data-g="{" ".join(self.P[i]["groups"])}" data-n="{escape(self.P[i]["name"].lower())}">', 1)
                for i in letters[l]) + "</ul>"
        body = f"""<h1>People</h1>
<p class="lede">{len(self.P):,} filmmakers, journalists, moderators, speakers and festival staff, from the catalogues and the festival website. Each page lists everything a person did at the festival, year by year, with their bios and the people they shared a stage with.</p>
<div class="chips">{groups}<a class="chip g" href="regulars.html">Regulars</a></div>
<div class="filter" data-target=".plist .pc"><label for="pf">Filter names</label><input id="pf" type="search" placeholder="Type a name">
<div class="fl"><span>Year:</span>{yrs}</div><div class="fl"><span>Role:</span>{gf}</div><p class="shown" aria-live="polite"></p></div>
<nav class="az" aria-label="A to Z">{az}</nav>
{blocks}"""
        self.page("people.html", "People", body, crumbs=[("index.html", "Home"), (None, "People")], active="people")

    def role_page(self, g):
        ids = sorted(self.group_people[g], key=lambda i: (-len(self.P[i]["years"]), sortname(self.P[i]["name"])))
        other = "".join(f'<a class="chip g{" on" if x == g else ""}" href="{x}.html">{escape(ROLE_GROUP_LABEL[x])} <span>{len(self.group_people[x])}</span></a>'
                        for x in GROUP_ORDER if self.group_people.get(x))
        by_year = defaultdict(set)
        for i in ids:
            for a in self.P[i]["appearances"]:
                if a.get("year") and ((a["type"] == "team" and g == "team") or (a["type"] != "team" and role_group_of(a["role"]) == g)):
                    by_year[a["year"]].add(i)
        mx = max([len(v) for v in by_year.values()] or [1])
        bars = "".join(f'<a class="bar" href="../years/{y}.html" title="{y}: {len(by_year.get(y, ()))}"><span style="height:{100 * len(by_year.get(y, ())) / mx:.0f}%"></span><i>{str(y)[2:]}</i></a>' for y in YEARS)
        body = f"""<h1>{escape(ROLE_GROUP_LABEL[g])}</h1><p class="lede">{escape(GROUP_BLURB[g])} {plural(len(ids), "person", "people")}, most editions first.</p>
<div class="chips">{other}</div>
<div class="bars" aria-label="People per year">{bars}</div>
<ul class="plist">{''.join(self.pcard(i, "../") for i in ids)}</ul>"""
        self.page(f"roles/{g}.html", ROLE_GROUP_LABEL[g], body, crumbs=[("index.html", "Home"), ("people.html", "People"), (None, ROLE_GROUP_LABEL[g])], active="people")

    def regulars(self):
        ids = [i for i in self.P if len(self.P[i]["years"]) >= 3]
        ids.sort(key=lambda i: (-len(self.P[i]["years"]), sortname(self.P[i]["name"])))
        rows = "".join(f'<tr><th scope="row">{self.plink(i, "")}</th><td>{self.years_strip(self.P[i]["years"], "")}</td><td class="n">{len(self.P[i]["years"])}</td><td>{escape(", ".join(ROLE_GROUP_LABEL.get(g, g) for g in self.P[i]["groups"][:3]))}</td></tr>' for i in ids)
        body = f"""<h1>Regulars</h1><p class="lede">{plural(len(ids), "person", "people")} who took part in three or more editions, as a filmmaker, speaker, moderator or member of the festival team.</p>
<div class="tablewrap"><table class="t reg"><thead><tr><th>Name</th><th>Editions</th><th class="n">#</th><th>Roles</th></tr></thead><tbody>{rows}</tbody></table></div>"""
        self.page("regulars.html", "Regulars", body, crumbs=[("index.html", "Home"), ("people.html", "People"), (None, "Regulars")], active="people")

    def person_page(self, pid):
        rel = "../"
        p = self.P[pid]
        by_year = defaultdict(list)
        for a in p["appearances"]:
            by_year[a.get("year") or 0].append(a)
        tl = ""
        for y in sorted(by_year, reverse=True):
            items = []
            for a in by_year[y]:
                role = a.get("role") or ""
                if a["type"] == "film" and a["id"] in self.F:
                    items.append(f'<li><span class="role">{escape(role.capitalize())}</span> {self.flink(a["id"], rel)}</li>')
                elif a["type"] == "session" and a["id"] in self.S:
                    s = self.S[a["id"]]
                    items.append(f'<li><span class="role">{escape(role.capitalize())}</span> {self.slink(a["id"], rel)} <span class="sub">{escape(KIND_LABEL.get(s.get("kind"), ""))}</span></li>')
                elif a["type"] == "team":
                    items.append(f'<li><span class="role">Festival team</span> {escape(role)}</li>')
                elif a["type"] == "award":
                    items.append(f'<li><span class="role">Honoree</span> {escape(a.get("label") or "Award")}{" — <cite>" + escape(a["film"]) + "</cite>" if a.get("film") else ""}</li>')
                elif a["type"] == "program":
                    items.append(f'<li><span class="role">Programme</span> {escape(role)}</li>')
            items = list(dict.fromkeys(items))
            ylabel = f'<a href="{rel}years/{y}.html">{y}</a>' if y else "Year not given"
            tl += f'<li class="ty"><h3>{ylabel}</h3><ul>{"".join(items)}</ul></li>'
        bios = p["bios"]
        bio_html = ""
        if bios:
            b0 = bios[0]
            src = self.bio_src(b0, rel)
            bio_html = f'<section class="bio"><h2>Biography</h2>{paras(b0["text"])}<p class="src">{src}</p>'
            if len(bios) > 1:
                bio_html += '<details><summary>Other bios (' + str(len(bios) - 1) + ")</summary>" + "".join(
                    f'<div class="ob">{paras(b["text"])}<p class="src">{self.bio_src(b, rel)}</p></div>' for b in bios[1:]) + "</details>"
            bio_html += "</section>"
        co = "".join(self.pcard(c, rel) for c in p["collaborators"][:12] if c in self.P)
        orgs = "".join(f'<a class="chip o" href="{rel}orgs/{o}.html">{escape(self.O[o]["label"])}</a>' for o in p["orgs"] if o in self.O)
        roles = "".join(f'<a class="chip g" href="{rel}roles/{g}.html">{escape(ROLE_GROUP_LABEL.get(g, g))}</a>' for g in p["groups"])
        srcs = []
        for u in p.get("dxfest_urls") or []:
            srcs.append(f'<a href="{u}">Festival website</a> (<a href="{wayback(u)}">archived</a>)')
        nyears = len(p["years"])
        body = f"""<div class="phead">{self.photo(pid, rel, "l")}<div>
<h1>{escape(p["name"])}</h1>
{f'<p class="aff">{escape(p["affiliation"])}</p>' if p.get("affiliation") else ""}
<p class="sub">{escape(self.person_role_line(pid))}</p>
<div class="chips">{roles}</div>
{self.years_strip(p["years"], rel)}
</div></div>
{f'<p class="note">Also listed as {escape(", ".join(p["variants"]))}.</p>' if p.get("variants") else ""}
<div class="cols"><div>
<section><h2>At the festival</h2><ol class="tl">{tl}</ol></section>
{bio_html}
</div><aside>
{f'<section><h2>Topics</h2><div class="chips">{self.tchips(p["topics"], rel, 10)}</div></section>' if p["topics"] else ""}
{f'<section><h2>Organisations in their bio</h2><div class="chips">{orgs}</div></section>' if orgs else ""}
{f'<section><h2>Shared a programme with</h2><ul class="plist one">{co}</ul></section>' if co else ""}
{f'<section><h2>Sources</h2><p class="src">{"<br>".join(srcs)}</p></section>' if srcs else ""}
</aside></div>"""
        desc = f'{p["name"]} at the Double Exposure Investigative Film Festival' + (f' ({nyears} edition{"s" if nyears != 1 else ""})' if nyears else "")
        self.page(f"people/{pid}.html", p["name"], body, desc=desc, crumbs=[("index.html", "Home"), ("people.html", "People"), (None, p["name"])], active="people")

    def bio_src(self, b, rel):
        if b["source"] == "catalogue":
            return "From the " + (self.cat_link(b["year"], b.get("page"), f'{b["year"]} catalogue, p. {b.get("page")}') or f'{b["year"]} catalogue')
        u = b.get("url")
        return f'From the <a href="{u}">festival website</a>' + (f' (<a href="{wayback(u)}">archived</a>)' if u else "") + (f', {b["year"]}' if b.get("year") else "")

    def films_index(self):
        ids = sorted(self.F, key=lambda i: (-max(self.F[i]["years"] or [0]), self.F[i]["title"].lower()))
        by_year = defaultdict(list)
        for i in ids:
            by_year[max(self.F[i]["years"] or [0])].append(i)
        yrs = "".join(f'<button type="button" class="chip y" data-y="{y}" aria-pressed="false">{y}</button>' for y in YEARS)
        tps = "".join(f'<button type="button" class="chip t" data-t="{t}" aria-pressed="false">{escape(self.T[t]["label"])}</button>'
                      for t in sorted(self.T, key=lambda t: -len(self.topic_films[t])) if self.topic_films[t])
        blocks = "".join(f'<h2 id="y{y}">{y} <a class="more" href="years/{y}.html">the {y} edition →</a></h2><ul class="fgrid">{"".join(self.fcard(i, "") for i in by_year[y])}</ul>' for y in sorted(by_year, reverse=True))
        body = f"""<h1>Films</h1>
<p class="lede">{len(self.F)} documentaries and shorts screened at Double Exposure, 2015–2026. Filter by year or topic, or browse <a href="countries.html">by country</a>.</p>
<div class="filter" data-target=".fgrid .fc"><label for="ff">Filter titles</label><input id="ff" type="search" placeholder="Type a title">
<div class="fl"><span>Year:</span>{yrs}</div><div class="fl"><span>Topic:</span>{tps}</div>
<div class="fl"><span>Length:</span><button type="button" class="chip s" data-s="0" aria-pressed="false">Features</button><button type="button" class="chip s" data-s="1" aria-pressed="false">Shorts</button></div><p class="shown" aria-live="polite"></p></div>
{blocks}"""
        self.page("films.html", "Films", body, crumbs=[("index.html", "Home"), (None, "Films")], active="films")

    def film_page(self, fid):
        rel = "../"
        f = self.F[fid]
        meta = [x for x in [f.get("country"), str(f["film_year"]) if f.get("film_year") else None,
                            f"{f['runtime_min']} min" if f.get("runtime_min") else None, "Short" if f.get("is_short") else None] if x]
        scr = ""
        for s in f["screenings"]:
            bits = [x for x in [s.get("slot"), s.get("premiere"), s.get("shorts_program"), nice_date(s.get("date")) if s.get("date") else None,
                                s.get("time"), s.get("venue")] if x]
            scr += f'<li><a href="{rel}years/{s["year"]}.html">{s["year"]}</a> {escape(" · ".join(bits))}' + (
                f'<span class="sub">{escape(s["after"])}</span>' if s.get("after") else "") + "</li>"
        ppl = defaultdict(list)
        for x in f["people"]:
            if x["person"] in self.P:
                ppl[x["role"]].append(x["person"])
        order = ["director", "co-director", "producer", "executive producer", "journalist", "subject", "moderator", "discussant", "panelist", "guest"]
        roles_html = ""
        for r in sorted(ppl, key=lambda r: order.index(r) if r in order else 50):
            ids = list(dict.fromkeys(ppl[r]))
            lab = r.capitalize() + ("s" if len(ids) > 1 and not r.endswith("s") else "")
            roles_html += f'<h3>{escape(lab)}</h3><ul class="plist one">{"".join(self.pcard(i, rel) for i in ids)}</ul>'
        sess = "".join(self.srow(s, rel) for s in self.film_sessions.get(fid, []))
        rel_f = Counter()
        for t in f["topics"]:
            for o in self.topic_films[t]:
                if o != fid:
                    rel_f[o] += 1
        more = [o for o, _ in sorted(rel_f.items(), key=lambda kv: (-kv[1], -max(self.F[kv[0]]["years"] or [0])))][:6]
        srcs = []
        if f.get("dxfest_url"):
            srcs.append(f'<a href="{f["dxfest_url"]}">Festival website</a> (<a href="{wayback(f["dxfest_url"])}">archived</a>)')
        for s in f["screenings"]:
            if s.get("page"):
                srcs.append(self.cat_link(s["year"], s["page"]))
        dirs = ", ".join(self.P[d]["name"] for d in f["directors"] if d in self.P)
        body = f"""<div class="fhead">{self.still(fid, rel)}<div>
<h1><cite>{escape(f["title"])}</cite></h1>
{f'<p class="by">Directed by {", ".join(self.plink(d, rel) for d in f["directors"] if d in self.P)}</p>' if f["directors"] else ""}
<p class="sub">{escape(" · ".join(meta))}</p>
{self.years_strip(f["years"], rel)}
<div class="chips">{self.tchips(f["topics"], rel)}</div>
</div></div>
<div class="cols"><div>
<section><h2>About the film</h2>{paras(f.get("synopsis")) or '<p class="note">No synopsis recorded.</p>'}</section>
<section><h2>At the festival</h2><ul class="scr">{scr}</ul></section>
{f'<section><h2>Sessions about this film</h2><ul class="slist">{sess}</ul></section>' if sess else ""}
</div><aside>
{f'<section><h2>People</h2>{roles_html}</section>' if roles_html else ""}
{f'<section><h2>Sources</h2><p class="src">{"<br>".join(x for x in srcs if x)}</p></section>' if srcs else ""}
</aside></div>
{f'<section><h2>More films on these topics</h2><ul class="fgrid">{"".join(self.fcard(o, rel) for o in more)}</ul></section>' if more else ""}"""
        self.page(f"films/{fid}.html", f["title"], body, desc=excerpt(f"{f['title']}{' by ' + dirs if dirs else ''}. {f.get('synopsis') or ''}", 200),
                  crumbs=[("index.html", "Home"), ("films.html", "Films"), (None, f["title"])], active="films")

    def countries_page(self):
        cs = sorted(self.countries, key=lambda c: (-len(self.countries[c]), c))
        body = '<h1>Films by country</h1><p class="lede">Production countries as the festival listed them. Films without a listed country are left out.</p>'
        body += '<nav class="az">' + "".join(f'<a href="#c-{slugify(c)}">{escape(c)} ({len(self.countries[c])})</a>' for c in cs) + "</nav>"
        for c in cs:
            body += f'<h2 id="c-{slugify(c)}">{escape(c)} <span class="count">{len(self.countries[c])}</span></h2><ul class="fgrid small">' + "".join(
                self.fcard(f, "") for f in sorted(self.countries[c], key=lambda i: -max(self.F[i]["years"] or [0]))) + "</ul>"
        self.page("countries.html", "Films by country", body, crumbs=[("index.html", "Home"), ("films.html", "Films"), (None, "Countries")], active="films")

    def sessions_index(self):
        ids = sorted(self.S, key=lambda i: (-self.S[i]["year"], self.S[i].get("date") or "9", time_key(self.S[i].get("time"))))
        kinds = Counter(self.S[i].get("kind") for i in ids)
        kf = "".join(f'<button type="button" class="chip k" data-k="{escape(k or "")}" aria-pressed="false">{escape(KIND_PLURAL.get(k, "Sessions"))} {n}</button>'
                     for k, n in kinds.most_common() if k)
        tps = "".join(f'<button type="button" class="chip t" data-t="{t}" aria-pressed="false">{escape(self.T[t]["label"])}</button>'
                      for t in sorted(self.T, key=lambda t: -len(self.topic_sessions[t])) if self.topic_sessions[t])
        by_year = defaultdict(list)
        for i in ids:
            by_year[self.S[i]["year"]].append(i)
        blocks = "".join(f'<h2 id="y{y}">{y} <span class="count">{len(by_year[y])}</span> <a class="more" href="years/{y}.html#schedule">schedule →</a></h2><ul class="slist">{"".join(self.srow(i, "", False) for i in by_year[y])}</ul>' for y in sorted(by_year, reverse=True))
        body = f"""<h1>Sessions</h1>
<p class="lede">{len(self.S)} panels, keynotes, workshops, pitches and events from the festival’s forum (called the Symposium until 2025), 2015–2026.</p>
<div class="filter" data-target=".slist .sr"><label for="sf">Filter titles</label><input id="sf" type="search" placeholder="Type a word">
<div class="fl"><span>Kind:</span>{kf}</div><div class="fl"><span>Topic:</span>{tps}</div><p class="shown" aria-live="polite"></p></div>
{blocks}"""
        self.page("sessions.html", "Sessions", body, crumbs=[("index.html", "Home"), (None, "Sessions")], active="sessions")

    def session_page(self, sid):
        rel = "../"
        s = self.S[sid]
        when = " · ".join(x for x in [nice_date(s.get("date")) if s.get("date") else str(s["year"]),
                                      (s.get("time") or "") + (f"–{s['end_time']}" if s.get("end_time") else "") or None, s.get("venue")] if x)
        ppl = defaultdict(list)
        for x in s["people"]:
            if x["person"] in self.P:
                ppl[x["role"]].append(x["person"])
        order = ["keynote", "moderator", "host", "panelist", "speaker", "presenter", "instructor"]
        roles_html = ""
        for r in sorted(ppl, key=lambda r: order.index(r) if r in order else 50):
            ids = list(dict.fromkeys(ppl[r]))
            lab = r.capitalize() + ("s" if len(ids) > 1 and not r.endswith("s") else "")
            roles_html += f'<h3>{escape(lab)}</h3><ul class="plist">{"".join(self.pcard(i, rel) for i in ids)}</ul>'
        films = "".join(self.fcard(f, rel) for f in s.get("films", []) if f in self.F)
        vids = "".join(f'<li><a href="{escape(v)}">{escape(v)}</a></li>' for v in s.get("videos") or [])
        relc = Counter()
        for t in s["topics"]:
            for o in self.topic_sessions[t]:
                if o != sid:
                    relc[o] += 1
        more = [o for o, _ in sorted(relc.items(), key=lambda kv: (-kv[1], abs(self.S[kv[0]]["year"] - s["year"])))][:8]
        srcs = []
        if s.get("dxfest_url"):
            srcs.append(f'<a href="{s["dxfest_url"]}">Festival website</a> (<a href="{wayback(s["dxfest_url"])}">archived</a>)')
        for src in s["sources"]:
            if src.get("kind") == "catalogue" and src.get("page"):
                srcs.append(self.cat_link(src["year"], src["page"]))
        sib = self.E[s["year"]]["sessions"]
        i = sib.index(sid)
        prev_ = f'<a href="{sib[i-1]}.html">← {escape(excerpt(self.S[sib[i-1]]["title"], 50))}</a>' if i > 0 else "<span></span>"
        next_ = f'<a href="{sib[i+1]}.html">{escape(excerpt(self.S[sib[i+1]]["title"], 50))} →</a>' if i + 1 < len(sib) else "<span></span>"
        body = f"""<p class="kindline">{escape(KIND_LABEL.get(s.get("kind"), "Session"))}{" · DX²" if s.get("track") else ""} · <a href="{rel}years/{s["year"]}.html#schedule">Double Exposure {s["year"]}</a></p>
<h1>{escape(s["title"])}</h1>
<p class="sub">{escape(when)}</p>
<div class="chips">{self.tchips(s["topics"], rel)}</div>
<div class="cols"><div>
<section>{paras(s.get("description")) or '<p class="note">No description recorded.</p>'}</section>
{f'<section><h2>Recording</h2><ul>{vids}</ul></section>' if vids else ""}
{f'<section><h2>Films discussed</h2><ul class="fgrid small">{films}</ul></section>' if films else ""}
{f'<section><h2>Sources</h2><p class="src">{"<br>".join(x for x in srcs if x)}</p></section>' if srcs else ""}
</div><aside>{f'<section><h2>People</h2>{roles_html}</section>' if roles_html else '<p class="note">No people recorded for this session.</p>'}</aside></div>
{f'<section><h2>Related sessions</h2><ul class="slist">{"".join(self.srow(o, rel) for o in more)}</ul></section>' if more else ""}
<div class="pager">{prev_}{next_}</div>"""
        self.page(f"sessions/{sid}.html", s["title"], body, desc=excerpt(f"{s['title']} ({s['year']}). {s.get('description') or ''}", 200),
                  crumbs=[("index.html", "Home"), ("sessions.html", "Sessions"), (f"years/{s['year']}.html", str(s["year"])), (None, excerpt(s["title"], 60))], active="sessions")

    def topics_index(self):
        rows = []
        for t in sorted(self.T, key=lambda t: -(len(self.topic_films[t]) + len(self.topic_sessions[t]))):
            ys = Counter(y for f in self.topic_films[t] for y in self.F[f]["years"]) + Counter(self.S[s]["year"] for s in self.topic_sessions[t])
            mx = max(ys.values() or [1])
            spark = "".join(f'<span style="height:{100 * ys.get(y, 0) / mx:.0f}%" title="{y}: {ys.get(y, 0)}"></span>' for y in YEARS)
            rows.append(f'<li><a href="topics/{t}.html"><b>{escape(self.T[t]["label"])}</b><span class="sub">{escape(self.T[t]["blurb"])}</span>'
                        f'<span class="sub2">{plural(len(self.topic_films[t]), "film")} · {plural(len(self.topic_sessions[t]), "session")} · {plural(len(self.topic_people[t]), "person", "people")}</span>'
                        f'<span class="spark" aria-hidden="true">{spark}</span></a></li>')
        body = f"""<h1>Topics</h1><p class="lede">Subjects the films and sessions deal with. Topics are assigned by keyword rules over titles, synopses and session descriptions, so they are a guide rather than a catalogue: a film can sit under several. The small chart shows each topic from 2015 to 2026.</p>
<ul class="topics">{''.join(rows)}</ul>"""
        self.page("topics.html", "Topics", body, crumbs=[("index.html", "Home"), (None, "Topics")], active="topics")

    def topic_page(self, t):
        rel = "../"
        T = self.T[t]
        films = sorted(self.topic_films[t], key=lambda i: (-max(self.F[i]["years"] or [0]), self.F[i]["title"]))
        sess = sorted(self.topic_sessions[t], key=lambda i: (-self.S[i]["year"], self.S[i]["title"]))
        pc = Counter()
        for f in self.topic_films[t]:
            for x in self.F[f]["people"]:
                pc[x["person"]] += 1
        for s in self.topic_sessions[t]:
            for x in self.S[s]["people"]:
                pc[x["person"]] += 1
        ppl = [p for p, _ in pc.most_common(36) if p in self.P]
        co = Counter()
        for f in self.topic_films[t]:
            co.update(x for x in self.F[f]["topics"] if x != t)
        for s in self.topic_sessions[t]:
            co.update(x for x in self.S[s]["topics"] if x != t)
        body = f"""<h1>{escape(T["label"])}</h1><p class="lede">{escape(T["blurb"])}</p>
<p class="sub">{plural(len(films), "film")} · {plural(len(sess), "session")} · {plural(len(pc), "person", "people")}</p>
{f'<p class="note">Often together with: {self.tchips([x for x, _ in co.most_common(6)], rel)}</p>' if co else ""}
<nav class="jump"><a href="#films">Films</a><a href="#sessions">Sessions</a><a href="#people">People</a></nav>
<section id="films"><h2>Films</h2><ul class="fgrid">{''.join(self.fcard(f, rel) for f in films) or '<li class="note">None.</li>'}</ul></section>
<section id="sessions"><h2>Sessions</h2><ul class="slist">{''.join(self.srow(s, rel) for s in sess) or '<li class="note">None.</li>'}</ul></section>
<section id="people"><h2>People most involved</h2><ul class="plist">{''.join(self.pcard(p, rel) for p in ppl)}</ul></section>"""
        self.page(f"topics/{t}.html", T["label"], body, desc=f'{T["label"]} at Double Exposure: films, sessions and people.',
                  crumbs=[("index.html", "Home"), ("topics.html", "Topics"), (None, T["label"])], active="topics")

    def orgs_index(self):
        by_kind = defaultdict(list)
        for o, O in self.O.items():
            if self.org_people.get(o):
                by_kind[O["kind"]].append(o)
        body = '<h1>Organisations</h1><p class="lede">News organisations, broadcasters, funders, universities and awards named in participants’ biographies. Follow one to see everyone at the festival connected with it.</p>'
        for k in ["news", "broadcast", "studio", "funder", "association", "research", "legal", "university", "award"]:
            if by_kind.get(k):
                body += f'<h2>{escape(ORG_KIND_LABEL[k])}</h2><div class="chips big">' + "".join(
                    f'<a class="chip o" href="orgs/{o}.html">{escape(self.O[o]["label"])} <span>{len(self.org_people[o])}</span></a>'
                    for o in sorted(by_kind[k], key=lambda o: -len(self.org_people[o]))) + "</div>"
        self.page("orgs.html", "Organisations", body, crumbs=[("index.html", "Home"), (None, "Organisations")], active="orgs")

    def org_page(self, o):
        rel = "../"
        ids = sorted(self.org_people[o], key=lambda i: (-len(self.P[i]["years"]), sortname(self.P[i]["name"])))
        body = f"""<h1>{escape(self.O[o]["label"])}</h1><p class="lede">{plural(len(ids), "person", "people")} whose festival biography mentions {escape(self.O[o]["label"])}. A mention can mean a job, a past job, a grant, a broadcast or an award: read the bio for which.</p>
<ul class="plist">{''.join(self.pcard(i, rel) for i in ids)}</ul>"""
        self.page(f"orgs/{o}.html", self.O[o]["label"], body, crumbs=[("index.html", "Home"), ("orgs.html", "Organisations"), (None, self.O[o]["label"])], active="orgs")

    def venues_index(self):
        vs = sorted(self.V.values(), key=lambda v: (-(len(v["films"]) + len(v["sessions"])), v["name"]))
        body = '<h1>Venues</h1><p class="lede">Where screenings and sessions took place, as the catalogues and website list them.</p><ul class="topics">' + "".join(
            f'<li><a href="venues/{v["id"]}.html"><b>{escape(v["name"])}</b><span class="sub2">{", ".join(map(str, v["years"]))} · {plural(len(v["films"]), "film")} · {plural(len(v["sessions"]), "session")}</span></a></li>' for v in vs) + "</ul>"
        self.page("venues.html", "Venues", body, crumbs=[("index.html", "Home"), (None, "Venues")], active="years")

    def venue_page(self, vid):
        rel = "../"
        v = self.V[vid]
        body = f"""<h1>{escape(v["name"])}</h1><p class="sub">{", ".join(f'<a href="{rel}years/{y}.html">{y}</a>' for y in v["years"])}</p>
{f'<section><h2>Films screened here</h2><ul class="fgrid small">{"".join(self.fcard(f, rel) for f in v["films"] if f in self.F)}</ul></section>' if v["films"] else ""}
{f'<section><h2>Sessions held here</h2><ul class="slist">{"".join(self.srow(s, rel) for s in sorted(v["sessions"], key=lambda i: (self.S[i]["year"], self.S[i].get("date") or "")) if s in self.S)}</ul></section>' if v["sessions"] else ""}"""
        self.page(f"venues/{vid}.html", v["name"], body, crumbs=[("index.html", "Home"), ("venues.html", "Venues"), (None, v["name"])], active="years")

    def search_page(self):
        body = """<h1>Search</h1>
<form class="bigsearch" role="search" onsubmit="return false"><label for="sq" class="vh">Search</label><input id="sq" type="search" placeholder="Name, film title, session, topic, organisation…" autocomplete="off"></form>
<p class="shown" aria-live="polite" id="sinfo"></p>
<div id="results"></div>
<noscript><p>Search needs JavaScript. Browse <a href="people.html">people</a>, <a href="films.html">films</a> or <a href="sessions.html">sessions</a> instead.</p></noscript>"""
        self.page("search.html", "Search", body, crumbs=[("index.html", "Home"), (None, "Search")], active="search")

    def search_index(self):
        rows = []
        for p in self.P.values():
            rows.append(["p", p["id"], p["name"], " ".join(p["variants"] + [p.get("affiliation") or ""] + [self.O[o]["label"] for o in p["orgs"]]),
                         self.person_role_line(p["id"])])
        for f in self.F.values():
            rows.append(["f", f["id"], f["title"], " ".join([self.P[d]["name"] for d in f["directors"] if d in self.P] + [f.get("country") or ""]),
                         f'{", ".join(map(str, f["years"]))} · ' + ", ".join(self.P[d]["name"] for d in f["directors"][:3] if d in self.P)])
        for s in self.S.values():
            rows.append(["s", s["id"], s["title"], " ".join(self.P[x["person"]]["name"] for x in s["people"] if x["person"] in self.P),
                         f'{s["year"]} · {KIND_LABEL.get(s.get("kind"), "Session")}'])
        for t, T in self.T.items():
            rows.append(["t", t, T["label"], T["blurb"], "Topic"])
        for o, O in self.O.items():
            if self.org_people.get(o):
                rows.append(["o", o, O["label"], "", f'Organisation · {plural(len(self.org_people[o]), "person", "people")}'])
        (PUBLIC / "search.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))

    def about(self):
        nf, ns, np_ = self.counts()
        cats = "".join(f'<li><a href="{self.E[y]["catalogue_wayback"]}">{y} catalogue</a></li>' for y in YEARS if self.E[y].get("catalogue_wayback"))
        body = f"""<h1>About this site</h1>
<p class="lede">The Double Exposure Explorer is an index of the people, films and sessions of the <a href="https://dxfest.com/">Double Exposure Investigative Film Festival</a> in Washington, DC, from its first edition in 2015 to its twelfth in 2026. It is an independent project of the Internet Archive’s Wayback Machine Labs, not a site of the festival or of 100Reporters, which runs it.</p>
<h2>What is here</h2>
<p>{nf} films, {ns} forum sessions and events, and {np_:,} people: filmmakers, journalists, moderators, panelists, workshop leaders, jurors and festival staff. Every person has a page listing what they did at the festival, year by year, their bios, the topics of their films and sessions, organisations named in their bio and the people they appeared with.</p>
<h2>Where it comes from</h2>
<ul>
<li><b>The printed festival catalogues</b> for 2015–2019 and 2022–2025, which the festival publishes as PDFs. Films, sessions, schedules, people and bios were read from them page by page; each record links to its catalogue page in the Wayback Machine. The 2024 catalogue’s text layer was broken and was read with OCR.</li>
<li><b>The festival website</b>, dxfest.com: its film pages for every year, its forum session pages (2016 and 2018–2026), and its 1,222 speaker biographies.</li>
<li>For 2020 and 2021, when the festival was held online and printed no catalogue, the website is the only source. Some 2020 programme pages were never captured by the Wayback Machine.</li>
</ul>
<p>Catalogues in the Wayback Machine:</p><ul class="cols3">{cats}</ul>
<h2>How it was put together, and its limits</h2>
<ul>
<li>The catalogue text was extracted into structured records with the help of an AI model, then merged with the website’s records. Names are matched across years by spelling; variants such as “Ramona Diaz” and “Ramona S. Diaz” are joined, but two different people with the same name would be shown as one, and one person whose name was spelled very differently may appear twice.</li>
<li>Topics are assigned by keyword rules and organisations are found by name in the bios. Both are aids to discovery, not judgements.</li>
<li>Roles are as the catalogue or website gave them. Where the website lists a speaker for a session without a role, they are shown as a speaker.</li>
</ul>
<p>Corrections are welcome: <a href="mailto:info@archive.org?subject=Double%20Exposure%20Explorer">info@archive.org</a>.</p>
<h2>Web archives</h2>
<p>Web archives are welcome to capture this site. If your crawler has trouble capturing it, contact info@archive.org. Every page is plain HTML with ordinary links, and there is a <a href="sitemap.xml">sitemap</a>.</p>
<h2 id="accessibility">Accessibility</h2>
<p>This site aims to meet WCAG 2.2 level AA: it has a skip link, labelled navigation and form fields, sufficient colour contrast in light and dark mode, and works with the keyboard and without JavaScript (except search and filtering). If something does not work for you, please <a href="mailto:info@archive.org?subject=Double%20Exposure%20Explorer%20accessibility">tell us</a>.</p>
<h2>Who made it</h2>
<p>This site was made by Claude, an AI model made by Anthropic, working in Claude Code at the direction of Mark Graham (Internet Archive). Mark Graham decided what it should be and what it should cover; Claude did the research and wrote the code.</p>
<p class="note">Built {date.today().isoformat()}.</p>"""
        self.page("about.html", "About", body, crumbs=[("index.html", "Home"), (None, "About")])

    def notfound(self):
        body = '<h1>Not found</h1><p>That page is not here. Try <a href="/dxfest/search.html">search</a> or the <a href="/dxfest/">home page</a>.</p>'
        self.page("404.html", "Not found", body)
        self.urls.remove("404.html")

    def sitemap(self):
        xs = "".join(f"<url><loc>{BASE_URL}{u}</loc></url>" for u in self.urls if u != "index.html")
        (PUBLIC / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{BASE_URL}</loc></url>{xs}</urlset>')


def ordinal(n):
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
            9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth"}.get(n, f"{n}th")


def sortname(n):
    parts = n.split()
    if len(parts) > 1 and parts[-1].lower().strip(".") in ("jr", "sr", "ii", "iii", "iv"):
        parts = parts[:-1]
    return (parts[-1] + " " + " ".join(parts[:-1])).lower() if parts else n.lower()


def time_key(t):
    if not t:
        return 9999
    m = re.match(r"(\d{1,2})(?::(\d\d))?\s*([ap])", t.strip(), re.I)
    if not m:
        return 9999
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return h * 60 + int(m.group(2) or 0)


def role_group_of(role):
    from .model import role_group
    return role_group(role)


if __name__ == "__main__":
    Site().build()
