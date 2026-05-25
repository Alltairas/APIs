"""Read matches.json and post a grouped HTML message to a Telegram chat.

Reads BOT_TOKEN and CHAT_ID from .env (or environment). Exits 0 if matches is
empty (no spam). Splits into multiple messages if total length > Telegram's
4096-char limit.
"""

import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

HERE = Path(__file__).resolve().parent
MATCHES_FILE = HERE / "matches.json"
ENV_FILE = HERE / ".env"
LOCAL_TZ = ZoneInfo("Europe/Paris")
DAYS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
TG_LIMIT = 4096
SOFT_LIMIT = 3800  # keep some buffer


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def fmt_showtime(st: dict) -> str:
    dt = datetime.fromisoformat(st["startDate"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    when = f"{DAYS_FR[dt.weekday()]} {dt.day:02d}/{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
    lang = "VF" if st.get("language") == "fr" else "VOST"
    extras = [lang]
    if st.get("format"):
        extras.append(st["format"])
    suffix = " · ".join(extras)
    url = st.get("ticketUrl")
    when_html = f'<a href="{html.escape(url)}">{when}</a>' if url else when
    return f"• {when_html} · {suffix}"


def build_film_block(film: dict) -> str:
    title = html.escape(film["title"])
    genres = ", ".join(html.escape(g) for g in film["genres"])
    lines = [f'🎥 <b><a href="{html.escape(film["url"])}">{title}</a></b>',
             f"<i>{genres}</i>"]
    for cinema in film["cinemas"]:
        lines.append("")
        lines.append(f'📍 <a href="{html.escape(cinema["url"])}">{html.escape(cinema["name"])}</a>')
        lines.extend(fmt_showtime(s) for s in cinema["showtimes"])
    return "\n".join(lines)


def chunk_messages(header: str, blocks: list[str]) -> list[str]:
    """Pack film blocks into messages without exceeding Telegram's size limit."""
    messages, current = [], header
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > SOFT_LIMIT and current and current != header:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def send(token: str, chat_id: str, text: str) -> None:
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    if not r.ok:
        sys.exit(f"Telegram API error {r.status_code}: {r.text}")


def main() -> int:
    load_env(ENV_FILE)
    token = os.environ.get("BOT_TOKEN")
    chat_ids = [c.strip() for c in os.environ.get("CHAT_ID", "").split(",") if c.strip()]
    if not token or not chat_ids:
        sys.exit("BOT_TOKEN and CHAT_ID must be set (see .env.example)")

    if not MATCHES_FILE.exists():
        sys.exit(f"{MATCHES_FILE} not found — run scraper.py first")

    films = json.loads(MATCHES_FILE.read_text(encoding="utf-8"))
    if not films:
        print("Aucun film à notifier — pas d'envoi.")
        return 0

    header = f"🎬 <b>Films à Strasbourg</b> — {len(films)} film(s)"
    blocks = [build_film_block(f) for f in films]
    messages = chunk_messages(header, blocks)

    for chat_id in chat_ids:
        for i, msg in enumerate(messages, 1):
            send(token, chat_id, msg)
            print(f"→ {chat_id}: message {i}/{len(messages)} ({len(msg)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
