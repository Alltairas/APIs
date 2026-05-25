# Strasbourg Cinémas — Scraper & Bot Telegram

Récupère les séances du jour des cinémas de Strasbourg depuis [timepilot.co](https://timepilot.co/cinemas/strasbourg), filtre par genre/langue/format, et expose les résultats via une CLI, un bot Telegram, et un fichier JSON.

## Fonctionnalités

- Scraping des 5 cinémas de Strasbourg (UGC Ciné Cité Étoile, Star, Cinéma Vox, Le Cosmos, Star Saint-Exupéry)
- Filtres combinables (logique AND) : genres, langue (VF/VOST), format (3D, IMAX)
- Tableau ASCII en terminal avec hyperliens OSC 8 cliquables (Ctrl/Cmd+clic ouvre la billetterie UGC, Cinéma Vox, etc.)
- Notification Telegram groupée vers un ou plusieurs chats (DM + groupes)
- Bot Telegram interactif (commandes `/scifi`, `/g`, `/lang`, `/fmt`, `/search`, `/all`)
- Whitelist des chats autorisés à dialoguer avec le bot
- Log quotidien horodaté (`YYYY-MM-DD_SCREENINGS.log`)

## Limites connues

- Seules les séances **du jour courant** sont récupérées (la page cinéma de timepilot ne sert que la date courante)
- Le bot fonctionne en long polling : nécessite qu'un process Python tourne en permanence
- Pas de cache entre runs : chaque commande déclenche 6 requêtes HTTP (~2-3 secondes de latence)

## Prérequis

- Python 3.9+ (utilise `zoneinfo` de la stdlib)
- Linux, macOS ou WSL (scripts en bash)
- Dépendances Python : `requests`, `beautifulsoup4`

## Installation

```bash
cd /chemin/vers/movie_seanses

python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4
```

Les scripts `run.sh` et `bot.sh` pointent vers `/home/aras/APIs/.venv/` par défaut. Adapte la variable `VENV_ACTIVATE` en haut de ces deux fichiers si ton chemin diffère.

## Configuration Telegram

1. Sur Telegram, contacte `@BotFather` :
   - `/newbot` → nom du bot → username (doit finir par `_bot`)
   - BotFather renvoie un **BOT_TOKEN** au format `123456789:AAH...`

2. Ouvre la conversation avec ton bot et envoie un message quelconque (`/start` ou `hello`). Telegram requiert ce premier contact côté utilisateur pour autoriser le bot à répondre.

3. Récupère ton **chat_id** personnel :
   ```bash
   curl -s "https://api.telegram.org/bot<TON_TOKEN>/getUpdates"
   ```
   Dans la réponse JSON, cherche `"chat":{"id":XXXXX,...}`. Ce nombre est ton chat_id (positif pour les DM).

4. Pour un groupe : ajoute le bot dedans, envoie une commande qui le mentionne (`/start@nom_du_bot`), puis relance `getUpdates`. Les id de groupes sont **négatifs** (ex. `-5252656259`).

5. Copie le template et remplis :
   ```bash
   cp .env.example .env
   ```
   ```
   BOT_TOKEN=123456789:AAH-ton-token-complet
   CHAT_ID=123456789,-987654321
   ```
   `CHAT_ID` accepte plusieurs valeurs séparées par des virgules — le bot enverra à toutes les destinations listées et n'acceptera de commandes que de leur part.

## Utilisation

### Mode CLI

```bash
./run.sh                                       # tous les films à l'affiche
./run.sh -g Science-Fiction --print            # filtre par genre + tableau terminal
./run.sh -g Science-Fiction Action -l VOST     # filtres combinés
./run.sh -l VF -f 3D --print                   # langue + format
./run.sh -g Science-Fiction --notify           # scrape puis envoie sur Telegram
```

Options du scraper :

| Flag | Description |
|---|---|
| `-g`, `--genres` | un ou plusieurs genres (voir liste plus bas) |
| `-l`, `--language` | `VF` ou `VOST` |
| `-f`, `--format` | `3D` ou `IMAX` |
| `--print` | affiche un tableau ASCII en terminal (heures cliquables) |
| `--notify` | (`run.sh` uniquement) chaîne `notify.py` après le scraping |

Genres acceptés : Musique, Romance, Animation, Fantastique, Comédie, Histoire, Drame, Science-Fiction, Action, Aventure, Horreur, Guerre, Documentaire, Policier, Thriller, Western.

Tous les filtres sont combinables — un film est conservé s'il matche **chacun** des filtres actifs. Sans aucun filtre, tous les films de la journée sont retournés.

### Mode bot Telegram

```bash
./bot.sh
```

Tant que le script tourne, envoie depuis Telegram (en DM ou dans un groupe whitelisté) :

| Commande | Effet |
|---|---|
| `/help`, `/start` | message d'aide |
| `/scifi` | raccourci pour Science-Fiction |
| `/all` | tous les films sans filtre |
| `/g Science-Fiction Action` | un ou plusieurs genres |
| `/lang VF` ou `/lang VOST` | filtre par langue |
| `/fmt 3D` ou `/fmt IMAX` | filtre par format |
| `/search g=Genre1,Genre2 lang=VOST fmt=3D` | filtres combinés en une commande |

Le bot répond dans le chat émetteur (DM ou groupe). `Ctrl+C` pour l'arrêter.

## Structure du projet

```
movie_seanses/
├── scraper.py       Scraper + CLI (argparse, JSON, tableau ASCII OSC 8)
├── notify.py        Lit matches.json et poste vers Telegram (HTML, multi-chat)
├── bot.py           Bot Telegram long polling + dispatcher de commandes
├── run.sh           Lanceur CLI (venv + log YYYY-MM-DD_SCREENINGS.log)
├── bot.sh           Lanceur bot (venv + log bot.log)
├── .env.example     Template des secrets (commitable)
├── .env             Secrets réels (gitignored)
├── .gitignore       Exclut .env, *.log, matches.json, __pycache__/
├── matches.json     Sortie du scraper (régénérée à chaque run)
└── README.md        Ce fichier
```

## Architecture

```
                  ┌──────────────┐
                  │ timepilot.co │
                  └──────┬───────┘
                         │ HTTPS (HTML + JSON-LD + SSR payload)
                         ▼
                  ┌─────────────┐
   CLI args ────▶ │  scraper.py │ ──▶ matches.json
                  └──────┬──────┘
                         │ import direct (in-process)
            ┌────────────┴────────────┐
            ▼                         ▼
     ┌────────────┐            ┌────────────┐
     │ notify.py  │            │   bot.py   │ ◀─── Telegram /commands
     └─────┬──────┘            └─────┬──────┘
           │                         │
           └──────────┬──────────────┘
                      ▼
              api.telegram.org
                  /sendMessage
```

- `scraper.py` expose ses fonctions (`fetch`, `list_cinemas`, `build_catalog`, `filter_catalog`, `serialize`) que `bot.py` réutilise par import direct — pas de subprocess, ce qui garde la latence sous 3 secondes.
- `notify.py` est utilisable seul (lit `matches.json`) ou via ses helpers (`build_film_block`, `chunk_messages`) appelés depuis `bot.py`.
- Les **ticketUrl** (URLs de billetterie UGC, Vox, Star, etc.) sont extraites du payload SSR par regex et propagées jusqu'au JSON et aux messages Telegram, où chaque horaire devient un lien cliquable.

## Sécurité

- `.env` est gitignored — ne le commit jamais. Si le BOT_TOKEN fuit, va sur `@BotFather` et envoie `/revoke` pour invalider immédiatement l'ancien.
- La whitelist `CHAT_ID` filtre les commandes : un chat non listé reçoit `Accès refusé` et ne déclenche aucun scraping ni envoi.
- HTML-escape systématique des contenus dynamiques (titres, noms de cinémas) avant injection dans les messages Telegram pour éviter toute interprétation parasite.

## Pistes d'évolution

- Cache local des pages scrapées (TTL court) pour réduire la charge sur timepilot
- Scraping multi-date (J+1, J+2…) en suivant les pages individuelles de chaque film
- Persistance entre runs (`seen_movies.json`) pour ne notifier que les nouveautés
- Hébergement 24/7 (tmux, systemd, ou cloud free-tier type Oracle Always Free)
- Support d'autres villes (paramétrer `CITY_URL`)
