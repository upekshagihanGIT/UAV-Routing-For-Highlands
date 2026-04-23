import folium

def init_map(coordinates):
    lat_sum = 0
    lon_sum = 0
    for coords in coordinates:
        lat_sum += coords[0]
        lon_sum += coords[1]

    avg_lat = lat_sum / len(coordinates)
    avg_lon = lon_sum / len(coordinates)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=16)

    return m

def add_marker_to_map(m, coordinate, color, text):
    folium.Marker(
        location=[coordinate[0], coordinate[1]],
        popup=text,
        icon=folium.Icon(color=color, icon='info-sign')
    ).add_to(m)

    m.save("map.html")