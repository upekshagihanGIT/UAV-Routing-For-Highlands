from routing_variables import ELEVATION
from calculations import random_location_around
from apis import get_elevation

def generate_new_location_with_low_elevation(base_location):
    radius = 1
    tries = 1
    new_lat, new_long = random_location_around(base_location[0], base_location[1], radius)
    elevation = get_elevation(new_lat, new_long)
    while elevation > ELEVATION:
        tries += 1
        new_lat, new_long = random_location_around(base_location[0], base_location[1], radius)
        elevation = get_elevation(new_lat, new_long)
        if tries == 10:
            radius += 1
            tries = 0
    return new_lat, new_long

def get_elevations_for_locations(locations):
    locations_with_elevations = []
    for location in locations:
        elevation = get_elevation(location[0], location[1])
        if elevation > ELEVATION:
            location = generate_new_location_with_low_elevation(location)
        locations_with_elevations.append((location, elevation))
    return locations_with_elevations