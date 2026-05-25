# ISS Tracker

A small Flask web app that shows the live position of the International Space Station on a Folium map, accumulates its ground track as a polyline, and lists the astronauts currently in orbit.

## Data sources

- **ISS position** — http://api.open-notify.org/iss-now.json
- **Astronauts** — [`astronauts.json`](astronauts.json), a local snapshot of the Open Notify `astros` endpoint, served on `/astronauts`.

## Project layout

```
iss_tracker_API/
├── app.py              # Flask server + routes
├── iss_logic.py        # Fetches ISS position, computes velocity (Haversine)
├── trace_manager.py    # In-memory store of the ISS ground track (GeoJSON)
├── astronauts.json     # Cached list of people currently in space
├── static/
│   └── images/         # astro1..4.jpg, cupola.jpg
└── templates/
    ├── index.html      # Live map + dashboard
    └── astronauts.html # Crew page
```

## Setup

Requires Python 3.10+.

1. Create and activate a virtual environment (named `myenv` so it matches the project's `.gitignore`):

   ```bash
   cd iss_tracker_API
   python3 -m venv myenv
   source myenv/bin/activate          # Linux / macOS / WSL
   # myenv\Scripts\activate           # Windows PowerShell
   ```

2. Install the dependencies:

   ```bash
   pip install flask requests folium
   ```

## Running

**Local** (default — binds to `127.0.0.1:8080`):

```bash
python3 app.py
```

Then open <http://127.0.0.1:8080> in a browser.

**Remote / VM** — bind to all interfaces by editing the last line of [`app.py`](app.py):

```python
app.run(host='0.0.0.0', port=8080)
```

**Detached** (keeps running after you log out of SSH):

```bash
nohup python3 app.py > app.log 2>&1 &
```

## Routes

| Method | Path            | Purpose                                                                 |
| ------ | --------------- | ----------------------------------------------------------------------- |
| GET    | `/`             | Live map (Folium + Realtime plugin)                                     |
| GET    | `/data`         | Current ISS position as a GeoJSON `Point` — polled by the map           |
| GET    | `/trace_feed`   | Accumulated ground track as a `LineString` — polled by the map          |
| GET    | `/telemetry`    | Current position + velocity; also appends a point to the track (heartbeat from the dashboard) |
| POST   | `/reset_trace`  | Clears the in-memory track                                              |
| GET    | `/astronauts`   | Crew page rendered from `astronauts.json`                               |

## Notes

- The track lives in memory only (see [`trace_manager.py`](trace_manager.py)); it is reset on every visit to `/` and on server restart.
- `app.log`, `nohup.out`, and `myenv/` are runtime artifacts and stay out of git (already covered by `.gitignore`).
