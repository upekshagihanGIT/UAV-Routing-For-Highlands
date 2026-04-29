from apis import get_weather
from calculations import bearing_from_coords, reverse_harvesine, haversine_m, get_optimal_direction
from variables import WIND_DIRECTION_THRESHOLD

def get_weather_for_locations(locations_with_elevation):
    latitudes = [lat for (lat, lon), elev in locations_with_elevation]
    longitudes = [lon for (lat, lon), elev in locations_with_elevation]
    elevations = [elev for (lat, lon), elev in locations_with_elevation]
    locations_with_weather = get_weather(latitudes, longitudes, elevations)
    return locations_with_weather

def check_intermediate_locations_weather(locations_with_weather):
    for idx in range(len(locations_with_weather)):
        if 0 < idx < len(locations_with_weather) - 1:
            locations_with_weather[idx] = evaluate_weather(locations_with_weather[idx-1], locations_with_weather[idx])
    return locations_with_weather

def evaluate_weather(from_location_weather, to_location_weather):
    to_location_weather_save = to_location_weather
    from_to_distance = haversine_m(
        from_location_weather[0][0],
        from_location_weather[0][1],
        to_location_weather[0][0],
        to_location_weather[0][1]
    )
    from_to_direction = bearing_from_coords(
        from_location_weather[0][0],
        from_location_weather[0][1],
        to_location_weather[0][0],
        to_location_weather[0][1]
    )
    optimal_direction = get_optimal_direction(from_to_direction, to_location_weather)
    while True:
        # wind direction
        wind_direction_ok = wind_direction_check(from_location_weather[0], to_location_weather[0], from_location_weather[2])
        if not wind_direction_ok:
            new_to_location = reverse_harvesine(
                to_location_weather_save[0][0],
                to_location_weather_save[0][1],
                from_to_distance,
                optimal_direction
            )
            new_to_location_with_weather = get_weather(
                [new_to_location[0]],[new_to_location[1]], [to_location_weather_save[1]]
            )
            to_location_weather = new_to_location_with_weather
            continue
    return to_location_weather

def wind_direction_check(from_coordinate, to_coordinate, wind_direction):
    bearing_direction = bearing_from_coords(
        from_coordinate[0], from_coordinate[1], to_coordinate[0], to_coordinate[1]
    )
    if wind_direction >= WIND_DIRECTION_THRESHOLD:
        wind_direction_min = wind_direction - WIND_DIRECTION_THRESHOLD
        wind_direction_max = wind_direction + WIND_DIRECTION_THRESHOLD
    else:
        wind_direction_min = wind_direction
        wind_direction_max = wind_direction + WIND_DIRECTION_THRESHOLD

    if wind_direction_min <= bearing_direction <= wind_direction_max:
        return True
    else:
        return False