"""Telegram bot for the Strasbourg cinema scraper.

Long-polling loop. Reuses scraper.py + notify.py functions in-process (no
subprocess) so each command runs in a few seconds. Whitelist of allowed chat
ids comes from .env (same CHAT_ID as notify.py). Run with `./bot.sh`.
"""

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import requests

import notify
import scraper

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
TG_API = "https://api.telegram.org/bot{token}/{method}"

HELP_TEXT = (
    "🎬 <b>Bot Strasbourg Cinémas</b>\n\n"
    "<b>Commandes :</b>\n"
    "/scifi — films Science-Fiction\n"
    "/all — tous les films à l'affiche\n"
    "/g &lt;Genre1&gt; [Genre2 …] — filtre par genre(s)\n"
    "/lang VF|VOST — filtre par langue\n"
    "/fmt 3D|IMAX — filtre par format\n"
    "/search g=Genre1,Genre2 lang=VF fmt=3D — filtres combinés\n"
    "/help — cette aide\n\n"
    f"<b>Genres :</b> {', '.join(scraper.ALLOWED_GENRES)}"
)


def send(token: str, chat_id: int, text: str) -> bool:
    """Send a message, log failures, never crash the bot."""
    try:
        r = requests.post(
            TG_API.format(token=token, method="sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if not r.ok:
            print(f"[send] {r.status_code} → {chat_id}: {r.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[send] net err → {chat_id}: {e}")
        return False


def make_args(genres=None, language=None, format=None):
    return SimpleNamespace(genres=genres, language=language, format=format)


def parse_command(text: str):
    """Return (kind, payload). kind ∈ {'help', 'query', 'error'}."""
    parts = text.strip().split()
    if not parts:
        return "error", "Commande vide."
    cmd = parts[0].lower().split("@", 1)[0]  # strip @bot_username in groups
    rest = parts[1:]

    if cmd in ("/start", "/help"):
        return "help", None
    if cmd == "/scifi":
        return "query", make_args(genres=["Science-Fiction"])
    if cmd == "/all":
        return "query", make_args()

    if cmd == "/g":
        if not rest:
            return "error", "Usage : /g &lt;Genre1&gt; [Genre2 …]"
        bad = [g for g in rest if g not in scraper.ALLOWED_GENRES]
        if bad:
            return "error", (
                f"Genres invalides : {', '.join(bad)}.\n"
                f"Valides : {', '.join(scraper.ALLOWED_GENRES)}"
            )
        return "query", make_args(genres=rest)

    if cmd == "/lang":
        if not rest or rest[0] not in scraper.ALLOWED_LANGUAGES:
            return "error", f"Usage : /lang {'|'.join(scraper.ALLOWED_LANGUAGES)}"
        return "query", make_args(language=rest[0])

    if cmd == "/fmt":
        if not rest or rest[0] not in scraper.ALLOWED_FORMATS:
            return "error", f"Usage : /fmt {'|'.join(scraper.ALLOWED_FORMATS)}"
        return "query", make_args(format=rest[0])

    if cmd == "/search":
        kv = {}
        for token in rest:
            if "=" in token:
                k, v = token.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        genres = None
        if "g" in kv:
            genres = [g for g in kv["g"].split(",") if g]
            bad = [g for g in genres if g not in scraper.ALLOWED_GENRES]
            if bad:
                return "error", f"Genres invalides : {', '.join(bad)}"
        lang = kv.get("lang")
        if lang and lang not in scraper.ALLOWED_LANGUAGES:
            return "error", f"lang doit être {'|'.join(scraper.ALLOWED_LANGUAGES)}"
        fmt = kv.get("fmt")
        if fmt and fmt not in scraper.ALLOWED_FORMATS:
            return "error", f"fmt doit être {'|'.join(scraper.ALLOWED_FORMATS)}"
        if not (genres or lang or fmt):
            return "error", "Précise au moins un filtre (g=, lang=, fmt=)."
        return "query", make_args(genres=genres, language=lang, format=fmt)

    return "error", f"Commande inconnue : {cmd}. /help pour la liste."


def run_query(args) -> list[dict]:
    cinemas = scraper.list_cinemas(scraper.fetch(scraper.CITY_URL))
    catalog = scraper.build_catalog(cinemas)
    filtered = scraper.filter_catalog(catalog, args)
    return scraper.serialize(filtered)


def format_results(films: list[dict], args) -> list[str]:
    if not films:
        return ["🎬 Aucun film ne correspond à ce filtre."]
    parts = []
    if args.genres:   parts.append(f"genres={'/'.join(args.genres)}")
    if args.language: parts.append(f"lang={args.language}")
    if args.format:   parts.append(f"fmt={args.format}")
    criterion = " · ".join(parts) if parts else "tout"
    header = f"🎬 <b>Films à Strasbourg</b> — {len(films)} film(s) [{criterion}]"
    blocks = [notify.build_film_block(f) for f in films]
    return notify.chunk_messages(header, blocks)


def handle_update(token: str, whitelist: set[int], upd: dict) -> None:
    msg = upd.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg.get("text") or ""

    if chat_id not in whitelist:
        label = msg["chat"].get("title") or msg["chat"].get("first_name") or "?"
        print(f"[deny] {chat_id} ({label}) → {text[:50]!r}")
        send(token, chat_id, "⛔ Accès refusé.")
        return

    if not text.startswith("/"):
        return  # ignore plain text silently

    kind, payload = parse_command(text)
    print(f"[cmd] {chat_id} → {text}")

    if kind == "help":
        send(token, chat_id, HELP_TEXT)
        return
    if kind == "error":
        send(token, chat_id, f"❌ {payload}")
        return

    try:
        films = run_query(payload)
    except requests.RequestException as e:
        send(token, chat_id, f"❌ Erreur réseau pendant le scraping : {e}")
        return

    messages = format_results(films, payload)
    for m in messages:
        send(token, chat_id, m)
    print(f"   ↳ {len(films)} film(s) → {len(messages)} message(s)")


def get_initial_offset(token: str) -> int | None:
    """Skip any messages buffered before the bot started (avoids replaying old /commands)."""
    try:
        r = requests.get(
            TG_API.format(token=token, method="getUpdates"),
            params={"offset": -1, "timeout": 0},
            timeout=10,
        )
        data = r.json()
        if data.get("ok") and data["result"]:
            return data["result"][-1]["update_id"] + 1
    except requests.RequestException as e:
        print(f"[init] impossible de récupérer l'offset initial : {e}")
    return None


def main() -> int:
    notify.load_env(ENV_FILE)
    token = os.environ.get("BOT_TOKEN")
    raw_ids = [c.strip() for c in os.environ.get("CHAT_ID", "").split(",") if c.strip()]
    try:
        whitelist = {int(c) for c in raw_ids}
    except ValueError:
        sys.exit(f"CHAT_ID doit contenir des entiers (séparés par virgule). Reçu : {raw_ids}")
    if not token or not whitelist:
        sys.exit("BOT_TOKEN et CHAT_ID requis dans .env")

    offset = get_initial_offset(token)
    print(f"Bot lancé. Whitelist: {sorted(whitelist)}")
    print(f"Offset initial: {offset} (les messages plus anciens seront ignorés)")
    print("Ctrl+C pour arrêter.\n")

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(
                TG_API.format(token=token, method="getUpdates"),
                params=params,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                print(f"[api] erreur : {data}")
                time.sleep(5)
                continue
            for upd in data["result"]:
                offset = upd["update_id"] + 1
                try:
                    handle_update(token, whitelist, upd)
                except Exception as e:
                    print(f"[handle] {type(e).__name__}: {e}")
        except KeyboardInterrupt:
            print("\nArrêt propre.")
            return 0
        except requests.RequestException as e:
            print(f"[net] {e} — retry dans 5s")
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
