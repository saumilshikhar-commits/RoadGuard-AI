#!/bin/bash

echo "Starting AI Pothole System..."

# start dashboard
python3 app_dashboard.py &

sleep 2

# open dashboard
open http://127.0.0.1:5001

# start map
python3 map_view.py

echo "System Running"