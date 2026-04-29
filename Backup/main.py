from variables import LOCATIONS
from routing import tsp, get_routes, print_solution
from maps import init_map, add_marker_to_map, add_arrow_to_map, add_text_to_map, add_circle_to_map
from calculations import calculate_coordinates
import time
from elevation_handling import get_elevations_for_locations
from weather_handling import get_weather_for_locations, check_weather
from concurrent.futures import ThreadPoolExecutor
from apis import get_elevation

MAX_WORKERS = 5

start_time = time.time()

locations = LOCATIONS.copy()

m = init_map(locations)

OPERATING_ELEVATION = max([get_elevation(location[0], location[1]) for location in locations])+30

INITIAL_TAKE_OFF_DISTANCE = OPERATING_ELEVATION - get_elevation(locations[0][0], locations[0][1])

solution, routing, manager, locations = tsp(locations)
locations_after_tsp = get_routes(solution, routing, manager, locations)[0]
routing_distance = print_solution(manager, routing, solution, locations)

time_now = time.time()
print(f"TSP Finished: {time_now - start_time:.2f}s")

intermediate_coordinates_list = []

for idx in range(len(locations_after_tsp)):
    # if not idx == len(locations_after_tsp) - 1:
    #     add_marker_to_map(m, locations_after_tsp[idx], "red", f"stop: {idx+1}", "map.html")
    #     add_text_to_map(m, locations_after_tsp[idx], "red", f"stop: {idx+1}", "map.html")
    # else:
    #     add_marker_to_map(m, locations_after_tsp[idx], "black", f"stop: 1, {idx+1}", "map.html")
    #     add_text_to_map(m, locations_after_tsp[idx], "black", f"stop: 1, {idx+1}", "map.html")
    if idx > 0:
        # add_arrow_to_map(m, locations_after_tsp[idx-1], locations_after_tsp[idx], "blue", "map.html")
        intermediate_coordinates = calculate_coordinates(locations_after_tsp[idx-1], locations_after_tsp[idx], routing_distance)
        intermediate_coordinates_list.append(intermediate_coordinates)
        #for idx2 in range(len(intermediate_coordinates)):
        #    add_circle_to_map(m, intermediate_coordinates[idx2], "darkred", f"intermediate stop: {idx2}", "map.html")

time_now = time.time()
print(f"Initial Map Finished: {time_now - start_time:.2f}s")

# with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#     locations_with_elevations = list(
#         executor.map(
#             lambda locations_list: get_elevations_for_locations(locations_list, OPERATING_ELEVATION),
#             intermediate_coordinates_list
#         )
#     )

# with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#     locations_with_weathers = list(
#         executor.map(
#             get_weather_for_locations,
#             locations_with_elevations
#         )
#     )

locations_with_elevations = get_elevations_for_locations(intermediate_coordinates_list[0], OPERATING_ELEVATION)
locations_with_weathers = get_weather_for_locations(locations_with_elevations)
check_weather(locations_with_weathers)

time_now = time.time()
print(f"Full process time: {time_now - start_time:.2f}s")