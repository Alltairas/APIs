# APIs, Scrapers & Bots

A collection of small projects built around public APIs and web scraping.

| Project | What it does | Stack |
|---------|--------------|-------|
| [`iss_tracker_API/`](iss_tracker_API) | Live ISS position on a map with its ground track, speed and current crew | Flask, Folium, Open Notify API |
| [`movie_seanses/`](movie_seanses) | Scrapes today's showtimes in Strasbourg cinemas, filters them and pushes them to Telegram | requests, BeautifulSoup, Telegram Bot API, GitHub Actions |
| [`weather_map/`](weather_map) | Real-time temperature heat map and population-density map of France's départements | OpenWeatherMap API, pandas, Plotly |

Some of these also run as live demos on my site: https://alltairas.github.io/

---

## ISS Tracker

A Flask app that shows the ISS position on a Folium map in real time. It builds the station's ground track
as a polyline and computes its speed with the Haversine formula. A second page lists the astronauts
currently in orbit.

```bash
cd iss_tracker_API
python3 -m venv myenv && source myenv/bin/activate
pip install flask requests folium
python3 app.py            # → http://127.0.0.1:8080
```

For routes and deployment notes, see [`iss_tracker_API/README.md`](iss_tracker_API/README.md).

## Strasbourg Cinema Showtimes

Scrapes [timepilot.co](https://timepilot.co/cinemas/strasbourg) for today's screenings at 5 Strasbourg
cinemas. You can filter by genre, language (VF/VOST) and format (3D/IMAX). Results are available as:

- a CLI with a clickable ASCII table,
- grouped Telegram notifications,
- an interactive Telegram bot (`/scifi`, `/g`, `/lang`, `/fmt`, `/search`, `/all`) with a chat whitelist,
- a `matches.json` file that a GitHub Actions workflow refreshes 3 times a day.

```bash
cd movie_seanses
pip install requests beautifulsoup4
cp .env.example .env      # add BOT_TOKEN and CHAT_ID
./run.sh -g Science-Fiction -l VOST --print
./bot.sh                  # start the Telegram bot
```

Full documentation (in French): [`movie_seanses/README.md`](movie_seanses/README.md)

## Weather Map of France

Two Jupyter notebooks:

- **`HeatMap_France.ipynb`** fetches the current weather for every French département from the
  [OpenWeatherMap](https://openweathermap.org/api) API. It converts temperatures (K → °C / °F) and local
  times, then draws an interactive Plotly choropleth using `France_deps.geojson`.
- **`DensityMap-France.ipynb`** draws a population-density choropleth from
  `departements-francais.csv`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install jupyter numpy pandas plotly pytz requests matplotlib
jupyter notebook
```

To use the heat map, put your OpenWeatherMap key in a text file and set `api_key_path` in the notebook to
that file. `weather_map/api_key.txt` is already excluded by `.gitignore`.

## Secrets

These files are never committed: `movie_seanses/.env`, `weather_map/api_key.txt`, and the virtual
environments.

## License

MIT (see [`weather_map/LICENSE`](weather_map/LICENSE))
