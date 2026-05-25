"""Scrape Strasbourg cinemas on timepilot.co.

Filters are combinable (AND). Omit all filters to list every film.
    python scraper.py --print
    python scraper.py -g Science-Fiction Action --print
    python scraper.py -g Science-Fiction -l VOST --print
    python scraper.py -l VF -f 3D --print

Output (matches.json): one entry per film matching the filters, with a
`cinemas` array merging every cinema where it screens + future showtimes.
Future = startDate >= now (UTC). The cinema page only lists today's showtimes;
later dates would require fetching per-film pages or a date query parameter.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://timepilot.co"
CITY_URL = f"{BASE}/cinemas/strasbourg"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
LOCAL_TZ = ZoneInfo("Europe/Paris")
DAYS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

ALLOWED_GENRES = [
    "Musique", "Romance", "Animation", "Fantastique", "Comédie",
    "Histoire", "Drame", "Science-Fiction", "Action", "Aventure",
    "Horreur", "Guerre", "Documentaire", "Policier", "Thriller", "Western",
]
ALLOWED_LANGUAGES = ["VF", "VOST"]
ALLOWED_FORMATS = ["3D", "IMAX"]


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def parse_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            out.append(json.loads(tag.string or ""))
        except json.JSONDecodeError:
            continue
    return out


def list_cinemas(html: str) -> list[dict]:
    for block in parse_jsonld(html):
        if block.get("@type") == "ItemList":
            return [
                {"name": it["item"]["name"], "url": it["item"]["url"]}
                for it in block["itemListElement"]
            ]
    return []


def extract_films(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    films: dict[str, dict] = {}
    for genre_span in soup.find_all("span", class_=re.compile(r"rounded-full")):
        node = genre_span
        for _ in range(10):
            node = node.parent
            if node is None:
                break
            link = node.find("a", href=re.compile(r"^/film/\d+"))
            if not link:
                continue
            title = link.get_text(strip=True)
            if not title:
                continue
            url = BASE + link["href"]
            genres = {
                s.get_text(strip=True)
                for s in node.find_all("span", class_=re.compile(r"rounded-full"))
            }
            entry = films.setdefault(url, {"title": title, "url": url, "genres": set()})
            entry["genres"] |= genres
            break
    return films


def normalize_format(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.lstrip("_")


def classify_language(showtime: dict) -> str:
    return "VF" if showtime.get("language") == "fr" else "VOST"


TICKET_RE = re.compile(
    r'startTime:"([^"]+)",language:"([^"]+)"[^}]*?ticketUrl:"([^"]+)"'
)


def extract_ticket_urls(html: str) -> dict[tuple[str, str], str]:
    """Map (startTime_ISO, SSR_lang) → ticketUrl from the SSR payload.
    SSR uses "VF" / "VO"; JSON-LD uses "fr" / null."""
    return {(m[0], m[1]): m[2] for m in TICKET_RE.findall(html)}


def extract_showtimes(html: str) -> dict[str, list[dict]]:
    tickets = extract_ticket_urls(html)
    by_film: dict[str, list[dict]] = {}
    now = datetime.now(timezone.utc)
    for block in parse_jsonld(html):
        for ev in block.get("@graph") or []:
            if ev.get("@type") != "ScreeningEvent":
                continue
            try:
                start = datetime.fromisoformat(ev["startDate"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if start < now:
                continue
            film_url = ev.get("workPresented", {}).get("@id")
            if not film_url:
                continue
            ssr_lang = "VF" if ev.get("inLanguage") == "fr" else "VO"
            by_film.setdefault(film_url, []).append({
                "startDate": ev["startDate"],
                "language": ev.get("inLanguage"),
                "format": normalize_format(ev.get("videoFormat")),
                "ticketUrl": tickets.get((ev["startDate"], ssr_lang)),
            })
    for showtimes in by_film.values():
        showtimes.sort(key=lambda s: s["startDate"])
    return by_film


def build_catalog(cinemas: list[dict]) -> dict[str, dict]:
    """Aggregate all films across cinemas: {film_url: {title, url, genres, cinemas:[...]}}."""
    catalog: dict[str, dict] = {}
    for c in cinemas:
        print(f"→ {c['name']}")
        page = fetch(c["url"])
        films = extract_films(page)
        showtimes_by_film = extract_showtimes(page)
        for f in films.values():
            showtimes = showtimes_by_film.get(f["url"], [])
            if not showtimes:
                continue
            entry = catalog.setdefault(f["url"], {
                "title": f["title"],
                "url": f["url"],
                "genres": set(),
                "cinemas": [],
            })
            entry["genres"] |= f["genres"]
            entry["cinemas"].append({
                "name": c["name"],
                "url": c["url"],
                "showtimes": showtimes,
            })
    return catalog


def filter_catalog(catalog: dict[str, dict], args) -> dict[str, dict]:
    """Apply -g / -l / -f as combined AND filters. Any subset can be active."""
    wanted_genres = set(args.genres) if args.genres else None
    kept: dict[str, dict] = {}

    for url, f in catalog.items():
        if wanted_genres and not (f["genres"] & wanted_genres):
            continue

        new_cinemas = []
        for c in f["cinemas"]:
            matching = [
                s for s in c["showtimes"]
                if (not args.language or classify_language(s) == args.language)
                and (not args.format or s.get("format") == args.format)
            ]
            if matching:
                new_cinemas.append({**c, "showtimes": matching})

        if new_cinemas:
            kept[url] = {**f, "cinemas": new_cinemas}
    return kept


def serialize(catalog: dict[str, dict]) -> list[dict]:
    return [
        {**v, "genres": sorted(v["genres"])}
        for v in sorted(catalog.values(), key=lambda x: x["title"])
    ]


def osc8(text: str, url: str | None) -> str:
    """Wrap text as an OSC 8 terminal hyperlink (ctrl/cmd-click to open)."""
    if not url:
        return text
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"


def print_table(catalog: list[dict]) -> None:
    headers = ["Film", "Cinéma", "Séance", "Langue", "Format"]
    # Each row stores cells + per-cell URL (None if no link).
    rows: list[tuple[list[str], list[str | None]]] = []
    for film in catalog:
        first = True
        for c in film["cinemas"]:
            for st in c["showtimes"]:
                dt = datetime.fromisoformat(st["startDate"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
                when = f"{DAYS_FR[dt.weekday()]} {dt.day:02d}/{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
                cells = [
                    film["title"] if first else "",
                    c["name"],
                    when,
                    classify_language(st),
                    st["format"] or "—",
                ]
                urls = [
                    film["url"] if first else None,
                    c["url"],
                    st.get("ticketUrl"),
                    None,
                    None,
                ]
                rows.append((cells, urls))
                first = False

    if not rows:
        print("(aucun résultat)")
        return

    widths = [max(len(h), max(len(r[0][i]) for r in rows)) for i, h in enumerate(headers)]
    sep_top = "┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    sep_mid = "├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
    sep_bot = "└" + "┴".join("─" * (w + 2) for w in widths) + "┘"

    def fmt_row(cells, urls=None):
        urls = urls or [None] * len(cells)
        parts = [f" {osc8(f'{c:<{w}}', u)} " for c, u, w in zip(cells, urls, widths)]
        return "│" + "│".join(parts) + "│"

    print(sep_top)
    print(fmt_row(headers))
    print(sep_mid)
    for cells, urls in rows:
        print(fmt_row(cells, urls))
    print(sep_bot)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scraper Timepilot — cinémas de Strasbourg. "
                    "Filtres combinables (AND). Omettre tout pour lister tout.",
    )
    p.add_argument("-g", "--genres", nargs="+", choices=ALLOWED_GENRES, metavar="GENRE",
                   help=f"Genre(s): {', '.join(ALLOWED_GENRES)}")
    p.add_argument("-l", "--language", choices=ALLOWED_LANGUAGES,
                   help="VF ou VOST.")
    p.add_argument("-f", "--format", choices=ALLOWED_FORMATS,
                   help="Format de projection.")
    p.add_argument("--print", dest="show_table", action="store_true",
                   help="Afficher un tableau structuré dans le terminal.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    print(f"→ {CITY_URL}")
    cinemas = list_cinemas(fetch(CITY_URL))
    print(f"  {len(cinemas)} cinémas\n")

    catalog = build_catalog(cinemas)
    catalog = filter_catalog(catalog, args)
    result = serialize(catalog)

    with open("matches.json", "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    parts = []
    if args.genres:   parts.append(f"genres={args.genres}")
    if args.language: parts.append(f"language={args.language}")
    if args.format:   parts.append(f"format={args.format}")
    criterion = " ∧ ".join(parts) if parts else "aucun (tout)"
    print(f"\n= {len(result)} film(s) | filtres: {criterion} → matches.json")

    if args.show_table:
        print()
        print_table(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
