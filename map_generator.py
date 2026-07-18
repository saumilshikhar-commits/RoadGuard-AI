import folium
import json

def generate_map():

    # center location (change if needed)
    m = folium.Map(location=[12.97, 77.59], zoom_start=12)

    try:
        with open("data.json", "r") as f:
            for line in f:
                data = json.loads(line)

                lat = data["lat"]
                lon = data["lon"]
                severity = data["severity"]

                color = "red" if severity == "high" else "orange"

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color=color,
                    fill=True
                ).add_to(m)

    except:
        print("No data yet")

    m.save("templates/map.html")