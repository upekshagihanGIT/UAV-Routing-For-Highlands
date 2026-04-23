import folium
from folium.plugins import AntPath

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
        tooltip=text,
        icon=folium.Icon(color=color, icon='info-sign')
    ).add_to(m)
    m.save("map.html")

def add_text_to_map(m, coordinate, color, text):
    folium.Marker(
        location=[coordinate[0], coordinate[1]],
        icon=folium.DivIcon(
            html=f'<div style="font-size:15px; color:{color}; white-space:nowrap;">{text}</div>',
            icon_size=(150, 36),
            icon_anchor=(0, 0)
        )
    ).add_to(m)
    m.save("map.html")

def add_circle_to_map(m, coordinate, color, text):
    folium.CircleMarker(
        location=[coordinate[0], coordinate[1]],
        radius=1,  # size in pixels
        color=color,  # border color
        fill=True,
        fill_color=color,
        fill_opacity=0.8,
        tooltip=text
    ).add_to(m)
    m.save("map.html")

def add_arrow_to_map(m, from_coordinate, to_coordinate, color):
    AntPath(
        locations=[list(from_coordinate), list(to_coordinate)],
        color=color,
        weight=3,
        opacity=0.8
    ).add_to(m)
    m.save("map.html")

def add_image_to_map(m, coordinate, text):
    folium.Marker(
        location=[coordinate[0], coordinate[1]],
        tooltip=text,
        icon=folium.CustomIcon(
            icon_image='path/to/small_icon.png',
            icon_size=(16, 16),  # width, height in pixels
            icon_anchor=(8, 8)  # center anchor
        )
    ).add_to(m)
    m.save("map.html")