#This file keeps your math separate so it doesn't clutter the server code.
import requests
import time
import math

# Initial state
state = {
    "lat": 0.0,
    "lon": 0.0,
    "vel": 0.0,
    "time": time.time()
}

def get_iss_data():
    global state
    try:
        r = requests.get("http://api.open-notify.org/iss-now.json", timeout=3).json()
        new_lat = float(r['iss_position']['latitude'])
        new_lon = float(r['iss_position']['longitude'])
        new_time = time.time()

        # Haversine Velocity Calculation
        R = 6371 + 428 # Earth radius km + mean altitude of iss according to the graph of https://github.com/fpedaccio/ISS_data 
        phi1, phi2 = math.radians(state["lat"]), math.radians(new_lat)
        dphi = math.radians(new_lat - state["lat"])
        dlambda = math.radians(new_lon - state["lon"])

        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        dist = R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))
        
        dt = (new_time - state["time"]) / 3600 # hours
        if dt > 0:
            state["vel"] = dist / dt
        
        state["lat"], state["lon"], state["time"] = new_lat, new_lon, new_time
    except Exception as e:
        print(f"API Error: {e}")
    
    return state
