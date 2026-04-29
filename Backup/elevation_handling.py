from calculations import random_location_around
from apis import get_elevation

def get_elevations_for_locations(locations, ELEVATION):
    locations_with_elevations = []
    for idx, location in enumerate(locations):
        elevation = get_elevation(location[0], location[1])
        if elevation > ELEVATION:
            location = generate_new_location_with_low_elevation(location, ELEVATION)
        locations_with_elevations.append((location, ELEVATION))
    return locations_with_elevations

def generate_new_location_with_low_elevation(base_location, ELEVATION):
    radius = 5
    tries = 1
    new_lat, new_long = random_location_around(base_location[0], base_location[1], radius)
    print(new_lat, new_long)
    elevation = get_elevation(new_lat, new_long)
    while elevation > ELEVATION:
        tries += 1
        new_lat, new_long = random_location_around(base_location[0], base_location[1], radius)
        elevation = get_elevation(new_lat, new_long)
        if tries == 5:
            radius += 5
            tries = 0
    return new_lat, new_long