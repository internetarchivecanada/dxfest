# Finding film posters

Input: batchN-input.json — films that screened at the Double Exposure Investigative Film Festival (Washington DC,
2015–2026), mostly investigative documentaries and shorts, with no poster found yet on Wikipedia.

Goal: for as many films as possible, find the film's real poster (theatrical/festival one-sheet or official key art in
portrait orientation). Be creative and fairly exhaustive. Places to look (use WebSearch / WebFetch / curl):
- the film's official website (og:image, press kit / EPK pages often link a poster JPG)
- distributors and sales agents (Dogwoof, Cinetic, Kino Lorber, Film Movement, Magnolia, Greenwich, Zeitgeist,
  Abramorama, Submarine, Autlook, Cat&Docs, CAT&Docs, First Hand Films, Java Films, Taskovski, MetFilm Sales…)
- broadcasters: PBS (POV, Independent Lens, FRONTLINE, Reel South, America ReFramed), HBO/Max, Netflix, Hulu,
  Showtime, Paramount+, National Geographic, Al Jazeera Witness, BBC Storyville, ARTE, Field of Vision, NYT Op-Docs,
  The Guardian docs, The New Yorker, Topic, Short of the Week, Vimeo Staff Picks
- other festivals' film pages (Sundance, Hot Docs, DOC NYC, IDFA, CPH:DOX, Sheffield DocFest, Tribeca, SXSW, Full
  Frame, True/False, Berlinale, Toronto, AFI Docs, Big Sky, Camden, DOK Leipzig, Thessaloniki, Visions du Réel…)
- film databases with public pages: TMDB (themoviedb.org film pages), Letterboxd, MUBI, JustWatch, FilmAffinity,
  Wikipedia in other languages, Wikimedia Commons
- the Wayback Machine (web.archive.org) for official sites or festival pages that have gone offline
- Do NOT use IMDb or Amazon image URLs (their terms forbid it).

Verify every hit: download the image (curl into your own scratch dir) and LOOK at it with the Read tool. Accept it
only if it is clearly the poster/key art for THIS film (title text on it matches, or the page it came from is
unambiguously this film by these directors). A wide still or a festival-branded promo card is not a poster — but
record a portrait key-art image if no one-sheet exists, with kind "key art". Short films often have no poster:
record nothing rather than guess.

Output: write batchN-output.json (valid JSON list), one entry per film you found:
  {"id": "<film id from input>", "title": "...", "image_url": "<direct URL of the image file>",
   "page_url": "<the page where you found it>", "source": "<short label, e.g. 'Official site', 'PBS POV', 'Hot Docs', 'TMDB'>",
   "kind": "poster" | "key art", "confidence": "high" | "medium", "note": "optional"}
Prefer the largest image up to ~1000px wide. Don't hotlink thumbnails of thumbnails if a bigger one is available.
Be gentle with sites: a second or so between requests to the same host.
Reply with: how many found of how many, and the films you could not find.
