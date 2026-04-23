from variables import LOCATIONS, MAX_WORKERS
from routing import tsp, get_routes, print_solution
from maps import init_map, add_marker_to_map, add_arrow_to_map, add_text_to_map, add_circle_to_map
from calculations import calculate_coordinates
import time
from elevation_handling import get_elevations_for_locations
from concurrent.futures import ThreadPoolExecutor
from apis import get_elevation

start_time = time.time()

locations = LOCATIONS.copy()

m = init_map(locations)

ELEVATION = max([get_elevation(location[0], location[1]) for location in locations]) + 30
print(f"ELEVATION: {ELEVATION:.2f}m")
exit()

solution, routing, manager, locations = tsp(locations)
locations_after_tsp = get_routes(solution, routing, manager, locations)[0]
routing_distance = print_solution(manager, routing, solution, locations)

for idx in range(len(locations_after_tsp)):
    if not idx == len(locations_after_tsp) - 1:
        add_marker_to_map(m, locations_after_tsp[idx], "red", f"stop: {idx+1}")
        add_text_to_map(m, locations_after_tsp[idx], "red", f"stop: {idx+1}")
    else:
        add_marker_to_map(m, locations_after_tsp[idx], "black", f"stop: 1, {idx+1}")
        add_text_to_map(m, locations_after_tsp[idx], "black", f"stop: 1, {idx+1}")
    if idx > 0:
        add_arrow_to_map(m, locations_after_tsp[idx-1], locations_after_tsp[idx], "blue")
        intermediate_coordinates = calculate_coordinates(locations_after_tsp[idx-1], locations_after_tsp[idx], routing_distance)
        for idx2 in range(len(intermediate_coordinates)):
            add_circle_to_map(m, intermediate_coordinates[idx2], "darkred", f"intermediate stop: {idx2}")
        locations_with_elevations = get_elevations_for_locations(intermediate_coordinates, ELEVATION)


# with ThreadPoolExecutor(max_workers=min(len(intermediate_coordinates_list), MAX_WORKERS)) as executor:
#     locations_with_elevations = list(executor.map(get_elevations_for_locations, intermediate_coordinates_list))

end_time = time.time()
print(f"Elapsed time: {end_time - start_time:.2f}s")