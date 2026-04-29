"""
disaster_scenarios.py
Defines disaster scenarios, delivery node priorities, and supply types
for UAV-assisted emergency logistics in Highland Cities.

Each scenario represents a realistic highland disaster event that affects
routing by adding urgency, restricting zones, and assigning supply priorities.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import IntEnum


# ─────────────────────────────────────────────
#  Priority levels (lower number = higher urgency)
# ─────────────────────────────────────────────
class Priority(IntEnum):
    CRITICAL = 1   # Medical / life-threatening (e.g., insulin, trauma kit)
    HIGH     = 2   # Food & water for isolated survivors
    MEDIUM   = 3   # Shelter materials, blankets
    LOW      = 4   # Non-urgent supplies


PRIORITY_LABELS = {
    Priority.CRITICAL : "🔴 CRITICAL – Medical",
    Priority.HIGH     : "🟠 HIGH – Food/Water",
    Priority.MEDIUM   : "🟡 MEDIUM – Shelter",
    Priority.LOW      : "🟢 LOW – General",
}

# Priority cost multiplier used in routing cost matrix:
# a CRITICAL delivery has a lower cost penalty → preferred earlier in route
PRIORITY_COST_MULTIPLIER = {
    Priority.CRITICAL : 0.5,
    Priority.HIGH     : 0.75,
    Priority.MEDIUM   : 1.0,
    Priority.LOW      : 1.25,
}


# ─────────────────────────────────────────────
#  Delivery Node
# ─────────────────────────────────────────────
@dataclass
class DeliveryNode:
    """A single delivery destination in a disaster scenario."""
    name        : str
    coordinates : Tuple[float, float]   # (lat, lon)
    priority    : Priority
    supply_type : str                   # human-readable supply description
    payload_kg  : float                 # kg to deliver
    notes       : str = ""              # optional context

    def priority_label(self) -> str:
        return PRIORITY_LABELS[self.priority]


# ─────────────────────────────────────────────
#  No-Fly / Restricted Zones
# ─────────────────────────────────────────────
@dataclass
class RestrictedZone:
    """
    Circular no-fly zone (e.g., military, rescue operation area).
    UAV must not fly within radius_m of the center.
    """
    name       : str
    center     : Tuple[float, float]   # (lat, lon)
    radius_m   : float
    reason     : str = ""


# ─────────────────────────────────────────────
#  Disaster Scenario
# ─────────────────────────────────────────────
@dataclass
class DisasterScenario:
    """
    A complete disaster scenario with delivery nodes,
    restricted zones, and operational constraints.
    """
    id                 : str
    name               : str
    description        : str
    depot              : Tuple[float, float]   # UAV base / origin
    delivery_nodes     : List[DeliveryNode]
    restricted_zones   : List[RestrictedZone] = field(default_factory=list)
    max_payload_kg     : float = 5.0           # UAV payload capacity
    battery_km         : float = 15.0          # max range per charge (km)
    operating_altitude_m: float = 30.0         # metres above terrain

    def all_locations(self) -> List[Tuple[float, float]]:
        """Returns depot + all delivery coordinates (for TSP)."""
        return [self.depot] + [n.coordinates for n in self.delivery_nodes]

    def priority_weights(self) -> List[float]:
        """
        Returns a cost multiplier per node (index 0 = depot).
        Used to bias the routing cost matrix so high-priority
        deliveries are visited earlier.
        """
        weights = [1.0]  # depot has no priority weight
        for node in self.delivery_nodes:
            weights.append(PRIORITY_COST_MULTIPLIER[node.priority])
        return weights

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"SCENARIO : {self.name}",
            f"{'='*60}",
            f"{self.description}",
            f"",
            f"Depot    : {self.depot}",
            f"Nodes    : {len(self.delivery_nodes)}",
            f"Payload  : {self.max_payload_kg} kg max",
            f"Range    : {self.battery_km} km",
            f"",
            f"{'─'*60}",
            f"{'#':<4} {'Name':<25} {'Priority':<30} {'Payload':>8}",
            f"{'─'*60}",
        ]
        for i, node in enumerate(self.delivery_nodes, 1):
            lines.append(
                f"{i:<4} {node.name:<25} {node.priority_label():<30} {node.payload_kg:>6.1f}kg"
            )
        if self.restricted_zones:
            lines += ["", f"Restricted Zones ({len(self.restricted_zones)}):"]
            for z in self.restricted_zones:
                lines.append(f"  • {z.name} — {z.reason} (r={z.radius_m}m)")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
#  SCENARIO 1 — Flash Flood (Nuwara Eliya, Sri Lanka highlands)
#  Road network cut off. UAVs are only supply link.
# ─────────────────────────────────────────────────────────────────
SCENARIO_FLOOD = DisasterScenario(
    id          = "FLOOD_01",
    name        = "Flash Flood – Nuwara Eliya Highlands",
    description = (
        "Heavy monsoon rains have caused flash flooding in the Nuwara Eliya "
        "district. Multiple mountain roads are submerged. Four communities are "
        "completely isolated. UAVs are the only viable supply delivery method."
    ),
    depot = (6.9497, 80.7891),   # Nuwara Eliya town (UAV base)
    delivery_nodes = [
        DeliveryNode(
            name        = "Ragala Village",
            coordinates = (6.9750, 80.8150),
            priority    = Priority.CRITICAL,
            supply_type = "Insulin, trauma kits, ORS sachets",
            payload_kg  = 3.0,
            notes       = "Diabetic patient reported; no road access"
        ),
        DeliveryNode(
            name        = "Dayagama Estate",
            coordinates = (6.9300, 80.8050),
            priority    = Priority.HIGH,
            supply_type = "Drinking water, ready-to-eat meals",
            payload_kg  = 4.5,
            notes       = "~80 residents, 3-day water supply needed"
        ),
        DeliveryNode(
            name        = "Peacock Hill",
            coordinates = (6.9600, 80.7700),
            priority    = Priority.HIGH,
            supply_type = "Baby formula, water purification tablets",
            payload_kg  = 2.5,
            notes       = "Infant family identified by local authority"
        ),
        DeliveryNode(
            name        = "Sita Eliya",
            coordinates = (6.9100, 80.7800),
            priority    = Priority.MEDIUM,
            supply_type = "Tarpaulins, blankets, rope",
            payload_kg  = 5.0,
            notes       = "Shelter damage reported"
        ),
    ],
    restricted_zones = [
        RestrictedZone(
            name     = "Military Relief Airspace",
            center   = (6.9450, 80.8000),
            radius_m = 300,
            reason   = "Army helicopter landing zone — active operations"
        ),
    ],
    battery_km           = 25.0,
    max_payload_kg       = 5.0,
    operating_altitude_m = 40.0,
)


# ─────────────────────────────────────────────────────────────────
#  SCENARIO 2 — Landslide (Kandy-Nuwara Eliya corridor)
#  Mountain landslide blocks main A5 highway.
# ─────────────────────────────────────────────────────────────────
SCENARIO_LANDSLIDE = DisasterScenario(
    id          = "SLIDE_01",
    name        = "Landslide – Kandy–Nuwara Eliya Corridor",
    description = (
        "A major landslide on the A5 highway near Ramboda has blocked all "
        "vehicular access to upper highland communities. Rescue teams are "
        "on site. UAVs must deliver medical and food supplies while the "
        "road is cleared (estimated 48 hours)."
    ),
    depot = (7.1500, 80.5500),   # Kandy forward base
    delivery_nodes = [
        DeliveryNode(
            name        = "Ramboda Upper",
            coordinates = (7.1200, 80.6000),
            priority    = Priority.CRITICAL,
            supply_type = "First-aid kits, stretchers, morphine",
            payload_kg  = 2.0,
            notes       = "Trapped workers from tea estate — injuries reported"
        ),
        DeliveryNode(
            name        = "Pussellawa Town",
            coordinates = (7.0800, 80.6300),
            priority    = Priority.HIGH,
            supply_type = "Food packs, clean water",
            payload_kg  = 4.0,
            notes       = "Town of ~400 cut off from supplies"
        ),
        DeliveryNode(
            name        = "Labukele Estate",
            coordinates = (7.0500, 80.6600),
            priority    = Priority.MEDIUM,
            supply_type = "Generator fuel, communication radio",
            payload_kg  = 3.5,
            notes       = "Estate has a small clinic — power backup critical"
        ),
        DeliveryNode(
            name        = "Kotmale Reservoir Side",
            coordinates = (7.1000, 80.5800),
            priority    = Priority.LOW,
            supply_type = "Sandbags, rope",
            payload_kg  = 5.0,
            notes       = "Preventive flood barrier reinforcement"
        ),
    ],
    restricted_zones = [
        RestrictedZone(
            name     = "Landslide Active Zone",
            center   = (7.1100, 80.5750),
            radius_m = 500,
            reason   = "Active debris flow — no fly zone for UAV safety"
        ),
        RestrictedZone(
            name     = "Rescue Helicopter Path",
            center   = (7.1250, 80.5900),
            radius_m = 200,
            reason   = "Medevac helicopter corridor"
        ),
    ],
    battery_km           = 40.0,
    max_payload_kg       = 5.0,
    operating_altitude_m = 50.0,   # higher terrain here
)


# ─────────────────────────────────────────────────────────────────
#  SCENARIO 3 — Earthquake (Badulla district)
#  Highland earthquake damages buildings & roads simultaneously.
# ─────────────────────────────────────────────────────────────────
SCENARIO_EARTHQUAKE = DisasterScenario(
    id          = "EQ_01",
    name        = "Earthquake – Badulla Highland District",
    description = (
        "A magnitude 5.8 earthquake has struck the Badulla district. "
        "Multiple villages in the highlands report structural collapses. "
        "Communications are partially down. UAVs are deployed for "
        "rapid damage assessment supply runs and medical delivery."
    ),
    depot = (6.9934, 81.0550),   # Badulla town (emergency ops center)
    delivery_nodes = [
        DeliveryNode(
            name        = "Haldummulla",
            coordinates = (6.8300, 80.9600),
            priority    = Priority.CRITICAL,
            supply_type = "Trauma kits, blood pressure meds, IV fluids",
            payload_kg  = 2.5,
            notes       = "Multiple casualties confirmed — building collapse"
        ),
        DeliveryNode(
            name        = "Boralanda",
            coordinates = (6.9100, 81.0000),
            priority    = Priority.CRITICAL,
            supply_type = "Emergency medication, splints",
            payload_kg  = 2.0,
            notes       = "Elderly care home — residents trapped on floor 2"
        ),
        DeliveryNode(
            name        = "Welimada",
            coordinates = (6.9000, 80.9200),
            priority    = Priority.HIGH,
            supply_type = "Water, high-energy biscuits",
            payload_kg  = 4.5,
            notes       = "Main market destroyed — food supply disrupted"
        ),
        DeliveryNode(
            name        = "Bandarawela",
            coordinates = (6.8300, 81.0000),
            priority    = Priority.MEDIUM,
            supply_type = "Tents, sleeping bags",
            payload_kg  = 5.0,
            notes       = "~200 residents displaced — temporary shelter needed"
        ),
        DeliveryNode(
            name        = "Diyatalawa",
            coordinates = (6.8000, 81.0300),
            priority    = Priority.LOW,
            supply_type = "Sanitation supplies, soap",
            payload_kg  = 3.0,
            notes       = "Preventive hygiene kit distribution"
        ),
    ],
    restricted_zones = [
        RestrictedZone(
            name     = "Collapsed Structure Zone",
            center   = (6.8300, 80.9600),
            radius_m = 150,
            reason   = "Active search & rescue — UAV must not hover overhead"
        ),
    ],
    battery_km           = 65.0,   # longer range drone for wider area
    max_payload_kg       = 5.0,
    operating_altitude_m = 35.0,
)


# ─────────────────────────────────────────────
#  Registry — easy lookup by scenario ID
# ─────────────────────────────────────────────
SCENARIOS = {
    SCENARIO_FLOOD.id      : SCENARIO_FLOOD,
    SCENARIO_LANDSLIDE.id  : SCENARIO_LANDSLIDE,
    SCENARIO_EARTHQUAKE.id : SCENARIO_EARTHQUAKE,
}

SCENARIOS_LIST = [SCENARIO_FLOOD, SCENARIO_LANDSLIDE, SCENARIO_EARTHQUAKE]


if __name__ == "__main__":
    for s in SCENARIOS_LIST:
        print(s.summary())
        print()
