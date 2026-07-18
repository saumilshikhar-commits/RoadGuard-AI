import folium
import json

# LOAD DATA
try:
    with open("detection_log.json", "r") as f:
        data = json.load(f)
except:
    data = []

# BASE MAP
m = folium.Map(location=[12.97, 77.59], zoom_start=13)

# STORE HEAT DATA
heat_data = []

for d in data:
    lat = d.get("lat", 12.97)
    lng = d.get("lng", 77.59)
    potholes = d.get("potholes", 1)

    # COLOR LOGIC
    if potholes <= 2:
        color = "green"
    elif potholes <= 5:
        color = "orange"
    else:
        color = "red"

    # MARKER
    folium.CircleMarker(
        location=[lat, lng],
        radius=8 + potholes,
        popup=f"Potholes: {potholes} | Time: {d.get('time')}",
        color=color,
        fill=True,
        fill_opacity=0.7
    ).add_to(m)

    # HEATMAP DATA
    heat_data.append([lat, lng, potholes])

# OPTIONAL: SIMPLE HEAT EFFECT USING CIRCLES (NO EXTRA LIBRARY)
for point in heat_data:
    folium.Circle(
        location=[point[0], point[1]],
        radius=point[2] * 30,
        color="red",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)

# SAVE OUTPUT
m.save("map.html")

print("Map updated: open map.html")