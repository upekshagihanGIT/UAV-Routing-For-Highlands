"""
main_disaster.py
────────────────────────────────────────────────────────────────
UAV-Assisted Emergency Logistics in Disaster Response
Highland Cities — Objective 2 Entry Point

Workflow
--------
1.  Select a disaster scenario
2.  Run priority-weighted, constraint-aware TSP routing
3.  Fetch real-time weather for all intermediate route points
4.  Apply elevation handling to ensure safe operating altitude
5.  Check weather constraints (wind, rain, visibility)
6.  Output a full disaster-response route report + HTML map

Usage
-----
    python main_disaster.py                  # interactive scenario menu
    python main_disaster.py --scenario FLOOD_01
    python main_disaster.py --scenario SLIDE_01
    python main_disaster.py --scenario EQ_01
    python main_disaster.py --list           # list all scenarios
"""

import argparse
import time
import sys

from disaster_scenarios import SCENARIOS, SCENARIOS_LIST
from routing import disaster_tsp, print_disaster_solution, get_disaster_route
from maps import init_map, add_marker_to_map, add_text_to_map, add_arrow_to_map, add_circle_to_map
from calculations import calculate_coordinates
from elevation_handling import get_elevations_for_locations
from weather_handling import get_weather_for_locations, check_weather
from apis import get_elevation


# ────────────────────────────────────────────
#  Map marker colours per priority
# ────────────────────────────────────────────
PRIORITY_COLORS = {
    1: "red",       # CRITICAL
    2: "orange",    # HIGH
    3: "beige",     # MEDIUM
    4: "green",     # LOW
    None: "black",  # DEPOT
}


def run_scenario(scenario_id: str, skip_weather: bool = False):
    """Run the full pipeline for a given disaster scenario."""

    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        print(f"Unknown scenario ID: {scenario_id}")
        print(f"Available: {list(SCENARIOS.keys())}")
        sys.exit(1)

    print(scenario.summary())
    start_time = time.time()

    # ── Step 1: Solve routing ──────────────────────────────────────
    print("\n[1/5] Solving disaster-response routing...")
    solution, routing_model, manager, locations, warnings = disaster_tsp(scenario)

    if solution is None:
        print("Routing failed. Exiting.")
        sys.exit(1)

    route, total_dist_m = print_disaster_solution(
        solution, routing_model, manager, locations, scenario, warnings
    )
    print(f"     Routing solved in {time.time() - start_time:.2f}s")

    # ── Step 2: Initialise map ─────────────────────────────────────
    print("[2/5] Initialising map...")
    m = init_map(locations)

    # Add depot marker
    depot_coord = scenario.depot
    add_marker_to_map(m, depot_coord, "black", "UAV Depot", "map_disaster.html")
    add_text_to_map(m, depot_coord, "black", "UAV Depot", "map_disaster.html")

    # Add delivery node markers
    for i, node in enumerate(scenario.delivery_nodes):
        color = PRIORITY_COLORS.get(int(node.priority), "blue")
        label = f"[P{int(node.priority)}] {node.name}"
        add_marker_to_map(m, node.coordinates, color, label, "map_disaster.html")
        add_text_to_map(m, node.coordinates, color, label, "map_disaster.html")

    # Draw route arrows
    route_coords = [stop['coordinates'] for stop in route]
    for i in range(1, len(route_coords)):
        add_arrow_to_map(m, route_coords[i-1], route_coords[i], "blue", "map_disaster.html")

    # ── Step 3: Elevation-based operating altitude ─────────────────
    print("[3/5] Calculating operating elevation...")
    max_elev = max(
        get_elevation(lat, lon) for lat, lon in locations
    )
    operating_elevation = max_elev + scenario.operating_altitude_m
    print(f"     Max terrain elevation : {max_elev:.1f} m")
    print(f"     Operating altitude    : {operating_elevation:.1f} m ASL")

    # ── Step 4 & 5: Weather check along route ─────────────────────
    if skip_weather:
        print("[4/5] Weather check skipped (--no-weather flag).")
    else:
        print("[4/5] Fetching weather for route intermediate points...")
        t4 = time.time()

        # Build intermediate coordinates for the first leg as a demo
        # (full pipeline would iterate all legs — extend here for Obj 3)
        all_intermediate = []
        for i in range(1, len(route_coords)):
            pts = calculate_coordinates(route_coords[i-1], route_coords[i], total_dist_m)
            all_intermediate.extend(pts)
            for pt in pts:
                add_circle_to_map(m, pt, "darkred", "weather check point", "map_disaster.html")

        print(f"     Intermediate check points : {len(all_intermediate)}")

        try:
            locs_with_elev = get_elevations_for_locations(all_intermediate, operating_elevation)
            locs_with_weather = get_weather_for_locations(locs_with_elev)

            print("[5/5] Checking weather constraints...")
            check_weather(locs_with_weather)
            print(f"     Weather check completed in {time.time() - t4:.2f}s")
        except Exception as e:
            print(f"     Weather API error (non-fatal): {e}")
            print("     Continuing without weather adjustment.")

    # ── Final output ───────────────────────────────────────────────
    m.save("map_disaster.html")
    elapsed = time.time() - start_time
    print(f"\n  Map saved  : map_disaster.html")
    print(f"  Total time : {elapsed:.2f}s")
    print(f"\n  Mission planning complete for scenario: {scenario.name}\n")

    return route, total_dist_m


# ────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────

def interactive_menu():
    print("\n" + "="*60)
    print("  UAV DISASTER RESPONSE — SCENARIO SELECTOR")
    print("="*60)
    for i, s in enumerate(SCENARIOS_LIST, 1):
        print(f"  {i}. [{s.id}]  {s.name}")
    print("="*60)
    choice = input("  Select scenario (1-3): ").strip()
    try:
        idx = int(choice) - 1
        return SCENARIOS_LIST[idx].id
    except (ValueError, IndexError):
        print("Invalid choice.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="UAV Disaster Response Routing"
    )
    parser.add_argument("--scenario", type=str, help="Scenario ID (e.g. FLOOD_01)")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--no-weather", action="store_true", help="Skip weather API calls")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        for s in SCENARIOS_LIST:
            print(f"  {s.id:<12}  {s.name}")
        sys.exit(0)

    scenario_id = args.scenario if args.scenario else interactive_menu()
    run_scenario(scenario_id, skip_weather=args.no_weather)
