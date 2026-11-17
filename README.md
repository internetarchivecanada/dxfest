# Double Exposure Explorer

An index of the films, forum sessions and people of the
[Double Exposure Investigative Film Festival](https://dxfest.com/) (Washington, DC, 2015–2026):
every film, panel, workshop and participant across the festival's twelve editions, with pages for
each person, film, session, year, topic, organisation and venue.

Live: https://wayback-labs.sf.archive.org/dxfest/ (Wayback Machine Labs studio, static tile `dxfest`).

## Sources

- **Festival catalogues** (PDF) for 2015–2019 and 2022–2025, linked from dxfest.com/past-catalogues and saved
  in the Wayback Machine. Their text (`pdftotext -layout`, page by page; Tesseract OCR for 2024, whose text layer
  is broken) was read into structured records, one JSON file per year in `data/catalogues/` following
  `data/catalogues/SCHEMA.md`. That extraction was done by Claude subagents reading every page; the
  `notes` field of each file records judgement calls and inconsistencies in the printed catalogues.
- **The festival website**: the WordPress REST API (`/wp-json/wp/v2/speakers`, `/conference`), the rendered film
  and session pages (`/films/<slug>/`, `/conference/<slug>/`) and speaker photos. 2020, 2021 and 2026 have no
  catalogue, so the website is their only source.

## Build

```
# raw/ (gitignored) holds the downloads: raw/pdf, raw/pages (page-split text), raw/web (REST dumps + pages)
python3 -m dx.web       # raw/web -> data/web.json
python3 -m dx.model     # data/catalogues/*.json + data/web.json -> data/festival.json
python3 -m dx.images    # film stills and speaker photos -> public/img/{f,p}/, data/images.json
python3 -m dx.site      # data/festival.json -> public/ (static site, committed)
```

Corrections: `data/aliases.tsv` (name variant → canonical name) and `data/not_people.txt`. Topics and the
organisation list are keyword rules in `dx/topics.py`. Rebuild after editing any of them.

## Deploy

The studio dir `/opt/services/dxfest` is a checkout of this repo (remote `canada`); Caddy serves `public/`.
Rebuild and commit `public/`, push `main`, then:

```
ssh wayback-labs.sf.archive.org sudo /opt/services/_scripts/deploy-tile plan dxfest --expect "$(git rev-parse HEAD)"
ssh wayback-labs.sf.archive.org sudo /opt/services/_scripts/deploy-tile deploy dxfest --expect "$(git rev-parse HEAD)"
```

The landing-page tile lives in internetarchivecanada/waybacklabs (`tiles/dxfest.menu`, `covers/dxfest-cover.jpg`).
