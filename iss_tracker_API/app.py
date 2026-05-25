from flask import Flask, render_template, jsonify, request
import folium
from folium.plugins import Realtime 
from folium.utilities import JsCode
import json
import os
from iss_logic import get_iss_data
import trace_manager  

app = Flask(__name__)

@app.route('/')
def index():
    # Clear old data when a new user lands on the page (optional but safer)
    trace_manager.reset_trace()
    
    try:
        iss_now = get_iss_data()
        
        # 1. Map Setup (Full Screen)
        m = folium.Map(
            location=[iss_now['lat'], iss_now['lon']], 
            zoom_start=3, 
            tiles="CartoDB positron", 
            attr='&copy; OpenStreetMap contributors &copy; CARTO',
            min_zoom=1,
            height="100%", 
            width="100%"
        )

        # 2. Existing Marker Layer (The Pin)
        rt_marker = Realtime(
            "/data",
            get_feature_id=JsCode("(f) => { return f.id }"),
            interval=5000
        )
        rt_marker.add_to(m)

        # 3. NEW: Trace Layer (The Red Line)
        # This polls /trace_feed every 5 seconds and draws the LineString
        rt_line = Realtime(
            "/trace_feed",
            get_feature_id=JsCode("(f) => { return f.id }"),
            interval=5000,
            # Simple JS style function to make the line red and thick
            style=JsCode("function(feature) { return {color: 'green', weight: 4, opacity: 0.7}; }")
        )
        rt_line.add_to(m)
        
        return render_template('index.html', map_div=m._repr_html_())
        
    except Exception as e:
        return f"Error creating map: {e}"

@app.route('/astronauts')
def astronauts():
    try:
        filename = os.path.join(app.root_path, 'astronauts.json')
        with open(filename, 'r') as f:
            data = json.load(f)
        return render_template('astronauts.html', people=data['people'], count=data['number'])
    except Exception as e:
        return f"Error: {e}"

@app.route('/data')
def data():
    # Only for the marker position
    info = get_iss_data()
    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": "iss",
            "geometry": {"type": "Point", "coordinates": [info["lon"], info["lat"]]},
            "properties": {"name": "ISS"}
        }]
    }
    return jsonify(geojson)

@app.route('/trace_feed')
def trace_feed():
    # Returns the accumulating line to the map
    return jsonify(trace_manager.get_geojson())

@app.route('/telemetry')
def telemetry():
    # Called by the Dashboard. We use this "heartbeat" to save the point.
    data = get_iss_data()
    
    # Add point to our Python storage
    trace_manager.add_point(data['lat'], data['lon'])
    
    return jsonify(data)

@app.route('/reset_trace', methods=['POST'])
def reset_route():
    # Called when window closes
    trace_manager.reset_trace()
    return "Reset", 200

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080, debug=True) # local host
