TP3/
├── app.py               # Main Flask server
├── iss_logic.py         # Backend math & API calls
├── astronauts.json
├── static/
│   └── images/
│       ├── astro1.jpg
│       ├── astro2.jpg
│       ├── astro3.jpg
│       └── astro4.jpg
└── templates/           # HTML folder (Required by Flask)
    ├── index.html       # Map + Dashboard (Main Page)
    └── astronauts.html  # Secondary Page

# Activate it (Linux/MacOS/Remote SSH)
source /home/ubuntu/TP3/myenv/bin/activate

# Install Required Packages
# With your .venv active, install the dependencies using pip:
    pip install flask requests folium

# Note: Ensure your app.py has app.run(host='0.0.0.0', port=8080) at the bottom.
# Activate server, quick test:  
    python3 app.py

# nohup python3 app.py 
 
