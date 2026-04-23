from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from calculations import haversine_m

def compute_distance_matrix(locations):
    """Creates callback to return distance between points."""
    distances = {}
    for from_counter, from_coordinate in enumerate(locations):
        distances[from_counter] = {}
        for to_counter, to_coordinate in enumerate(locations):
            if from_counter == to_counter:
                distances[from_counter][to_counter] = 0
            else:
                # harversine
                distances[from_counter][to_counter] = haversine_m(
                    from_coordinate[0], from_coordinate[1], to_coordinate[0], to_coordinate[1]
                )
    return distances


def get_routes(solution, routing, manager, locations):
    """Get vehicle routes from a solution and store them in an array."""
    # Get vehicle routes and store them in a two-dimensional array whose
    # i,j entry is the jth location visited by vehicle i along its route.
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
    """Prints solution on console."""
    print(f"Objective: {solution.ObjectiveValue()}")
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
    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(locations), 1, 0
    )

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    distance_matrix = compute_distance_matrix(locations)

    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    # Print solution on console.
    if solution:
        global ROUTING_DISTANCE
        ROUTING_DISTANCE = print_solution(manager, routing, solution, locations)
        return get_routes(solution, routing, manager, locations)[0]
    else:
        return None