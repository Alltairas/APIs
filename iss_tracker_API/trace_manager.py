# trace_manager.py
# Handles the storage of coordinates for the ISS path

# Global list to store [longitude, latitude] points
# Note: GeoJSON uses [Lon, Lat], while Leaflet uses [Lat, Lon].
trace_points = []

def add_point(lat, lon):
    """Adds a new coordinate to the trace."""
    # Avoid adding duplicate points if the ISS hasn't moved enough
    if not trace_points or trace_points[-1] != [lon, lat]:
        trace_points.append([lon, lat])

def get_geojson():
    """Returns the path as a GeoJSON LineString Feature."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "iss_path",  # Fixed ID so Realtime updates the same line
                "properties": {"stroke": "red"}, # Simple property for potential styling
                "geometry": {
                    "type": "LineString",
                    "coordinates": trace_points
                }
            }
        ]
    }

def reset_trace():
    """Clears the history."""
    global trace_points
    trace_points = []
