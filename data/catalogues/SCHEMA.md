# Catalogue extraction schema (one JSON file per festival year)

File: ~/tmp/dxfest/data/catalogues/<YEAR>.json  (UTF-8, pretty-printed, valid JSON)

{
  "year": 2017,
  "edition_name": "Double Exposure Investigative Film Festival & Symposium",   // as the catalogue names it
  "dates": "October 19-22, 2017",            // as printed
  "theme": null,                              // festival theme/tagline if printed, else null
  "venues": [{"name": "...", "address": "..."}],
  "films": [{
      "title": "TRUST WHO",                  // title case it properly: "Trust WHO"
      "directors": ["Lilian Franck"],
      "country": "Germany",                   // as printed, null if absent
      "film_year": 2017,                      // production year, null if absent
      "runtime_min": 85,
      "premiere": "World Premiere",           // e.g. World/North American/US/East Coast/DC Premiere, null
      "slot": "Opening Night",                // Opening Night / Centerpiece / Closing Night / Spotlight / name of shorts program, else null
      "is_short": false,
      "shorts_program": null,                 // name of the shorts block this film screened in, if any
      "screening": {"date": "2017-10-22", "time": "1:00 PM", "venue": "..."},   // ISO date if derivable from the catalogue
      "synopsis": "full synopsis text, verbatim, joined into paragraphs",
      "after_screening": "Discussion with filmmaker to follow screening",  // verbatim note, null if none
      "people": [{"name": "Lilian Franck", "role": "director"},
                 {"name": "...", "role": "producer|moderator|discussant|panelist|subject|journalist|editor|cinematographer|..."}],
      "page": 23                              // catalogue page number (the "=== PAGE n ===" marker)
  }],
  "sessions": [{                              // symposium/forum panels, keynotes, workshops, masterclasses, pitch sessions,
      "title": "...",                         // award ceremonies, conversations, receptions/parties, special events
      "kind": "panel|keynote|workshop|masterclass|conversation|pitch|award|screening-event|reception|other",
      "date": "2017-10-20", "time": "10:00 AM", "end_time": "11:15 AM", "venue": "...",
      "description": "verbatim description",
      "people": [{"name": "...", "role": "moderator|panelist|speaker|keynote|presenter|host|instructor|juror|honoree"}],
      "related_films": ["Trust WHO"],         // films the session discusses, if any
      "page": 31
  }],
  "people": [{                                 // EVERY person with a bio in the catalogue (speakers, filmmakers, moderators, jurors)
      "name": "Mike Rezendes",
      "bio": "verbatim bio paragraph",
      "affiliation": "The Associated Press",   // main current employer/outlet if clear, else null
      "page": 40
  }],
  "awards": [{"name": "...", "recipient": "...", "film": null, "description": "...", "page": 5}],
  "organizers": [{"name": "...", "role": "Festival Director"}],   // festival staff, board, advisory committee, programmers, jury (role says which)
  "notes": "anything odd: pages that were unreadable, sections skipped, uncertain readings"
}

Rules
- Read the whole page-split text file; do not skim. Do not invent anything: every value must come from the catalogue text. Use null for unknowns.
- Names exactly as printed but in normal capitalisation ("SELINA LEWIS DAVIDSON" -> "Selina Lewis Davidson"). Strip honorifics only if purely decorative.
- Fix obvious text-extraction artefacts (hyphenation across lines, broken ligatures, OCR noise) but do not paraphrase.
- Layout text may interleave two columns; untangle it carefully, especially in bio pages where two bios sit side by side.
- Sponsors/funders logos: skip. Ads: skip. Letters from the director: skip (but take the theme if stated).
- When a session lists people only by name with titles, put the title/outlet into that person's people[] entry if no bio exists (bio may be the short "Name, Title, Outlet" line).
- Validate with: python3 -c "import json;json.load(open('<file>'))"
