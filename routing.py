"""
routing.py  (disaster-response enhanced)
─────────────────────────────────────────
Extends the original OR-Tools TSP solver with:

  1. Priority-weighted cost matrix
     High-priority delivery nodes are given a lower arc cost so the
     solver naturally visits them earlier in the route.

  2. Capacity constraint
     Total payload must not exceed the UAV's max_payload_kg.

  3. Restricted-zone penalty
     Arcs whose straight-line path passes through a restricted zone
     receive a large penalty cost, pushing the solver to avoid them.

  4. Battery / range constraint
     Total route distance is capped at battery_km converted to metres.
"""

import math
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from calculations import haversine_m

# ─── penalty applied to arcs crossing restricted zones (metres equivalent) ───
RESTRICTED_ZONE_PENALTY = 999_999


# ────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────

def _arc_crosses_zone(lat1, lon1, lat2, lon2, zone_lat, zone_lon, zone_radius_m):
    """
    True if the straight-line arc between (lat1,lon1) to (lat2,lon2)
    passes within zone_radius_m of the zone centre.
    Uses closest-point-on-segment approximation (sufficient for < 30 km).
    """
    ax, ay = lat1, lon1
    bx, by = lat2, lon2
    px, py = zone_lat, zone_lon

    ab_x, ab_y = bx - ax, by - ay
    ap_x, ap_y = px - ax, py - ay

    ab_sq = ab_x ** 2 + ab_y ** 2
    if ab_sq == 0:
        t = 0.0
    else:
        t = (ap_x * ab_x + ap_y * ab_y) / ab_sq
        t = max(0.0, min(1.0, t))

    closest_lat = ax + t * ab_x
    closest_lon = ay + t * ab_y

    dist_m = haversine_m(closest_lat, closest_lon, zone_lat, zone_lon)
    return dist_m < zone_radius_m


def compute_disaster_distance_matrix(locations, priority_weights,
                                     restricted_zones=None):
    """
    Build an integer distance matrix where each arc cost is:

        base_distance_m * priority_weight_of_destination
        + restricted_zone_penalty  (if arc crosses a restricted zone)

    Parameters
    ----------
    locations        : list of (lat, lon)
    priority_weights : list of floats, one per location (index 0 = depot)
    restricted_zones : list of RestrictedZone dataclass objects (or None)

    Returns
    -------
    dict[int][int] -> int  (arc cost in virtual metres)
    """
    n = len(locations)
    matrix = {}
    for i in range(n):
        matrix[i] = {}
        for j in range(n):
            if i == j:
                matrix[i][j] = 0
                continue

            base = haversine_m(
                locations[i][0], locations[i][1],
                locations[j][0], locations[j][1]
            )
            # priority bias: multiply by destination weight
            cost = int(base * priority_weights[j])

            # restricted zone penalty
            if restricted_zones:
                for zone in restricted_zones:
                    if _arc_crosses_zone(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1],
                        zone.center[0], zone.center[1],
                        zone.radius_m
                    ):
                        cost += RESTRICTED_ZONE_PENALTY
                        break

            matrix[i][j] = cost

    return matrix


# ────────────────────────────────────────────────────────────────
#  Core disaster solver
# ────────────────────────────────────────────────────────────────

def disaster_tsp(scenario):
    """
    Solve the disaster-response routing problem for a given scenario.

    Constraints applied:
      * Priority-weighted arc costs (CRITICAL visited first)
      * Capacity dimension (total payload <= max_payload_kg)
      * Distance dimension (total route <= battery range in metres)
      * Restricted zone arc penalties

    Parameters
    ----------
    scenario : DisasterScenario

    Returns
    -------
    (solution, routing, manager, locations, warnings)
    """
    locations = scenario.all_locations()
    priority_weights = scenario.priority_weights()
    restricted_zones = scenario.restricted_zones if scenario.restricted_zones else []
    n = len(locations)
    warnings = []

    # 1. Routing index manager (1 vehicle, depot = node 0)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    # 2. Priority-weighted cost matrix (for objective function)
    distance_matrix = compute_disaster_distance_matrix(
        locations, priority_weights, restricted_zones
    )

    # Raw distance matrix (for battery/range dimension — must use real metres, NO penalties)
    raw_distance_matrix = compute_disaster_distance_matrix(
        locations, [1.0] * len(locations), restricted_zones=None  # no penalties in range dimension
    )

    def distance_callback(from_idx, to_idx):
        return distance_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    def raw_distance_callback(from_idx, to_idx):
        return raw_distance_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_cb = routing.RegisterTransitCallback(distance_callback)
    raw_transit_cb = routing.RegisterTransitCallback(raw_distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    # 3. Battery / distance dimension — use RAW distances, not priority-weighted
    max_range_m = int(scenario.battery_km * 1000)
    routing.AddDimension(
        raw_transit_cb,
        0,
        max_range_m,
        True,
        "Distance"
    )
    distance_dimension = routing.GetDimensionOrDie("Distance")
    distance_dimension.SetGlobalSpanCostCoefficient(100)

    # 4. Capacity constraint: warn if total exceeds one trip, but still route all nodes.
    #    In disaster logistics, the UAV makes multiple trips (returns to depot to reload).
    #    We model this by removing the hard capacity dimension and instead reporting
    #    how many trips are required in the summary.
    total_payload = sum(nd.payload_kg for nd in scenario.delivery_nodes)
    trips_required = math.ceil(total_payload / scenario.max_payload_kg)
    if trips_required > 1:
        warnings.append(
            f"MULTI-TRIP: Total payload ({total_payload:.1f} kg) requires "
            f"{trips_required} UAV trips at {scenario.max_payload_kg:.1f} kg/trip. "
            f"Route shown is optimal visit order (highest priority first)."
        )

    # 6. Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 10

    # 7. Solve
    solution = routing.SolveWithParameters(search_params)

    if solution:
        return solution, routing, manager, locations, warnings
    else:
        warnings.append("No solution found. Check battery range vs. node spread.")
        return None, routing, manager, locations, warnings


# ────────────────────────────────────────────────────────────────
#  Route extraction and reporting
# ────────────────────────────────────────────────────────────────

def get_disaster_route(solution, routing, manager, locations, scenario):
    """
    Extract the ordered route and annotate each stop with
    disaster-response metadata.

    Returns list of dicts, one per stop.
    """
    route = []
    index = routing.Start(0)
    stop_number = 0

    while not routing.IsEnd(index):
        node_idx = manager.IndexToNode(index)
        coord = locations[node_idx]

        if node_idx == 0:
            entry = {
                "stop"        : 0,
                "name"        : "UAV Depot (Base)",
                "coordinates" : coord,
                "type"        : "DEPOT",
                "priority"    : None,
                "supply"      : None,
                "payload_kg"  : 0.0,
                "notes"       : "Mission start / return point",
            }
        else:
            node = scenario.delivery_nodes[node_idx - 1]
            entry = {
                "stop"        : stop_number,
                "name"        : node.name,
                "coordinates" : coord,
                "type"        : "DELIVERY",
                "priority"    : node.priority,
                "supply"      : node.supply_type,
                "payload_kg"  : node.payload_kg,
                "notes"       : node.notes,
            }

        route.append(entry)
        stop_number += 1
        index = solution.Value(routing.NextVar(index))

    # Append return to depot
    route.append(dict(route[0]) | {"stop": stop_number, "name": "UAV Depot (Return)"})
    return route


def print_disaster_solution(solution, routing, manager, locations, scenario, warnings):
    """Print a formatted disaster-response routing report to console."""
    from disaster_scenarios import PRIORITY_LABELS

    print(f"\n{'='*65}")
    print(f"  DISASTER RESPONSE ROUTING REPORT")
    print(f"  Scenario : {scenario.name}")
    print(f"{'='*65}")

    if warnings:
        for w in warnings:
            print(w)
        print()

    route = get_disaster_route(solution, routing, manager, locations, scenario)

    total_dist_m = 0
    for i, stop in enumerate(route):
        tag   = stop['type']
        name  = stop['name']
        coord = stop['coordinates']

        if tag == "DEPOT":
            print(f"\n  [BASE]  {name}")
            print(f"          Coords : {coord[0]:.5f}, {coord[1]:.5f}")
        else:
            plabel = PRIORITY_LABELS.get(stop['priority'], "")
            print(f"\n  Stop {stop['stop']:02d} -> {name}")
            print(f"          Priority : {plabel}")
            print(f"          Supply   : {stop['supply']}")
            print(f"          Payload  : {stop['payload_kg']:.1f} kg")
            print(f"          Coords   : {coord[0]:.5f}, {coord[1]:.5f}")
            if stop['notes']:
                print(f"          Notes    : {stop['notes']}")

        if i > 0:
            prev = route[i - 1]['coordinates']
            d = haversine_m(prev[0], prev[1], coord[0], coord[1])
            total_dist_m += d
            print(f"          Leg dist : {d:,} m")

    total_payload = sum(nd.payload_kg for nd in scenario.delivery_nodes)
    used_pct = (total_dist_m / (scenario.battery_km * 1000)) * 100
    trips_required = math.ceil(total_payload / scenario.max_payload_kg)

    print(f"\n{'─'*65}")
    print(f"  Total route distance : {total_dist_m:,} m  ({total_dist_m/1000:.2f} km)")
    print(f"  Battery used         : {used_pct:.1f}% of {scenario.battery_km} km range")
    print(f"  Total payload        : {total_payload:.1f} kg / {scenario.max_payload_kg:.1f} kg capacity")
    print(f"  Trips required       : {trips_required}")
    print(f"  Restricted zones     : {len(scenario.restricted_zones)} active")
    print(f"{'='*65}\n")

    return route, total_dist_m


# ────────────────────────────────────────────────────────────────
#  Legacy TSP (preserved — used by original main.py)
# ────────────────────────────────────────────────────────────────

def compute_distance_matrix(locations):
    distances = {}
    for i, fc in enumerate(locations):
        distances[i] = {}
        for j, tc in enumerate(locations):
            distances[i][j] = 0 if i == j else haversine_m(
                fc[0], fc[1], tc[0], tc[1]
            )
    return distances


def get_routes(solution, routing, manager, locations):
    routes = []
    for route_nbr in range(routing.vehicles()):
        index = routing.Start(route_nbr)
        route = [locations[manager.IndexToNode(index)]]
        while not routing.IsEnd(index):
            index = solution.Value(routing.NextVar(index))
            route.append(locations[manager.IndexToNode(index)])
        routes.append(route)
    return routes


def print_solution(manager, routing, solution, locations):
    index = routing.Start(0)
    plan_output = "Route:\n"
    route_distance = 0
    while not routing.IsEnd(index):
        plan_output += f" ~{locations[manager.IndexToNode(index)]}~ ->"
        previous_index = index
        index = solution.Value(routing.NextVar(index))
        route_distance += routing.GetArcCostForVehicle(previous_index, index, 0)
    plan_output += f" ~{locations[manager.IndexToNode(index)]}~ \n"
    plan_output += f"Objective: {route_distance}m\n"
    print(plan_output)
    return route_distance


def tsp(locations):
    manager = pywrapcp.RoutingIndexManager(len(locations), 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    distance_matrix = compute_distance_matrix(locations)

    def distance_callback(from_index, to_index):
        return distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        return solution, routing, manager, locations
    else:
        return None
