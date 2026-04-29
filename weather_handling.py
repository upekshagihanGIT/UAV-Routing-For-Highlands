"""
weather_handling.py
────────────────────────────────────────────────────────────────
Evaluates ALL 12 weather parameters returned by the Open-Meteo API
against UAV operational thresholds tuned for Highland environments.

Parameters checked (index in weather tuple):
  Index  Variable               Unit
  ─────  ────────────────────── ───────
    0    (lat, lon)             –
    1    elevation              m
    2    wind_direction_180m    degrees (0–360)
    3    temperature_180m       °C
    4    relative_humidity_2m   %
    5    wind_speed_180m        km/h
    6    precipitation          mm
    7    rain                   mm
    8    showers                mm
    9    snowfall               cm
   10    weather_code           WMO code
   11    pressure_msl           hPa
   12    cloud_cover_high       %
   13    visibility             m

UAV Operational Thresholds (Highland context):
  - Wind speed       : ≤ 35 km/h          (strong wind causes instability at altitude)
  - Wind direction   : within ±20° of bearing (headwind/tailwind manageable, crosswind not)
  - Precipitation    : ≤ 2.5 mm           (light rain acceptable, heavy rain grounds UAV)
  - Rain             : ≤ 2.0 mm
  - Showers          : ≤ 1.5 mm
  - Snowfall         : ≤ 0.5 cm           (any snowfall is high risk at highland altitudes)
  - Visibility       : ≥ 1000 m           (minimum visual/sensor range for safe navigation)
  - Temperature      : -5°C to 45°C       (battery performance degrades outside this range)
  - Humidity         : ≤ 95%              (extreme humidity affects electronics & motors)
  - Pressure (MSL)   : ≥ 900 hPa          (low pressure = thin air = reduced lift in highlands)
  - Cloud cover high : ≤ 90%              (heavy cloud cover at altitude = icing risk)
  - Weather code     : blocks on WMO codes for storms, heavy rain, fog, snow, thunderstorms
"""

from apis import get_weather
from calculations import bearing_from_coords, reverse_harvesine, haversine_m, get_optimal_direction
from variables import WIND_DIRECTION_THRESHOLD

# ─────────────────────────────────────────────────────────────
#  Thresholds
# ─────────────────────────────────────────────────────────────

THRESHOLDS = {
    "wind_speed_kmh"       : 35.0,    # km/h — max safe UAV wind speed in highlands
    "precipitation_mm"     : 2.5,     # mm   — total precipitation limit
    "rain_mm"              : 2.0,     # mm   — rain limit
    "showers_mm"           : 1.5,     # mm   — shower limit
    "snowfall_cm"          : 0.5,     # cm   — any snowfall is dangerous at altitude
    "visibility_m"         : 1000.0,  # m    — minimum visibility for safe operation
    "temperature_min_c"    : -5.0,    # °C   — battery failure risk below this
    "temperature_max_c"    : 45.0,    # °C   — motor/battery overheating above this
    "humidity_max_pct"     : 95.0,    # %    — electronics/motor risk above this
    "pressure_min_hpa"     : 900.0,   # hPa  — thin air reduces UAV lift below this
    "cloud_cover_high_pct" : 90.0,    # %    — icing risk above this
}

# WMO weather codes that ground the UAV entirely
# Ref: https://open-meteo.com/en/docs (WMO Weather interpretation codes)
BLOCKED_WEATHER_CODES = {
    # Fog
    45, 48,
    # Heavy drizzle / freezing drizzle
    57, 67,
    # Heavy rain
    65, 67,
    # Heavy freezing rain
    66, 67,
    # Snow (moderate to heavy)
    73, 75, 77,
    # Rain showers (violent)
    82,
    # Snow showers (heavy)
    86,
    # Thunderstorm
    95, 96, 99,
}

# Human-readable descriptions for WMO codes (for reporting)
WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

# Severity levels for reporting
SEVERITY_OK      = "OK"
SEVERITY_WARNING = "WARNING"
SEVERITY_BLOCKED = "BLOCKED"


# ─────────────────────────────────────────────────────────────
#  Named tuple-like accessor for weather tuple
# ─────────────────────────────────────────────────────────────

def _parse(w):
    """
    Unpack a weather tuple from get_weather() into a named dict.
    Tuple structure (from apis.py):
        (lat,lon), elev, wind_dir, temp, humidity, wind_speed,
        precipitation, rain, showers, snowfall, weather_code,
        pressure_msl, cloud_cover_high, visibility
    """
    return {
        "coords"           : w[0],
        "elevation"        : w[1],
        "wind_direction"   : w[2],
        "temperature"      : w[3],
        "humidity"         : w[4],
        "wind_speed"       : w[5],
        "precipitation"    : w[6],
        "rain"             : w[7],
        "showers"          : w[8],
        "snowfall"         : w[9],
        "weather_code"     : int(w[10]),
        "pressure_msl"     : w[11],
        "cloud_cover_high" : w[12],
        "visibility"       : w[13],
    }


# ─────────────────────────────────────────────────────────────
#  Individual parameter checks
#  Each returns (severity, message)
# ─────────────────────────────────────────────────────────────

def check_wind_speed(wind_speed_kmh):
    t = THRESHOLDS["wind_speed_kmh"]
    if wind_speed_kmh > t:
        return SEVERITY_BLOCKED, f"Wind speed {wind_speed_kmh:.1f} km/h exceeds limit ({t} km/h)"
    elif wind_speed_kmh > t * 0.8:
        return SEVERITY_WARNING, f"Wind speed {wind_speed_kmh:.1f} km/h approaching limit ({t} km/h)"
    return SEVERITY_OK, f"Wind speed {wind_speed_kmh:.1f} km/h — OK"


def check_wind_direction(from_coord, to_coord, wind_direction_deg):
    """
    Checks if wind direction is within acceptable range of the flight bearing.
    A headwind/tailwind (within ±WIND_DIRECTION_THRESHOLD degrees of bearing)
    is acceptable. A crosswind outside this range is blocked.
    """
    bearing = bearing_from_coords(
        from_coord[0], from_coord[1],
        to_coord[0],   to_coord[1]
    )
    diff = abs(bearing - wind_direction_deg) % 360
    if diff > 180:
        diff = 360 - diff   # normalise to 0–180

    if diff <= WIND_DIRECTION_THRESHOLD:
        return SEVERITY_OK, (
            f"Wind direction {wind_direction_deg:.0f}° / Bearing {bearing:.0f}° "
            f"— aligned (diff {diff:.0f}°)"
        )
    elif diff <= WIND_DIRECTION_THRESHOLD * 2:
        return SEVERITY_WARNING, (
            f"Wind direction {wind_direction_deg:.0f}° / Bearing {bearing:.0f}° "
            f"— moderate crosswind (diff {diff:.0f}°)"
        )
    else:
        return SEVERITY_BLOCKED, (
            f"Wind direction {wind_direction_deg:.0f}° / Bearing {bearing:.0f}° "
            f"— severe crosswind (diff {diff:.0f}°)"
        )


def check_precipitation(precip_mm):
    t = THRESHOLDS["precipitation_mm"]
    if precip_mm > t:
        return SEVERITY_BLOCKED, f"Precipitation {precip_mm:.1f} mm exceeds limit ({t} mm)"
    elif precip_mm > t * 0.6:
        return SEVERITY_WARNING, f"Precipitation {precip_mm:.1f} mm — approaching limit"
    return SEVERITY_OK, f"Precipitation {precip_mm:.1f} mm — OK"


def check_rain(rain_mm):
    t = THRESHOLDS["rain_mm"]
    if rain_mm > t:
        return SEVERITY_BLOCKED, f"Rain {rain_mm:.1f} mm exceeds limit ({t} mm)"
    elif rain_mm > t * 0.6:
        return SEVERITY_WARNING, f"Rain {rain_mm:.1f} mm — approaching limit"
    return SEVERITY_OK, f"Rain {rain_mm:.1f} mm — OK"


def check_showers(showers_mm):
    t = THRESHOLDS["showers_mm"]
    if showers_mm > t:
        return SEVERITY_BLOCKED, f"Showers {showers_mm:.1f} mm exceeds limit ({t} mm)"
    return SEVERITY_OK, f"Showers {showers_mm:.1f} mm — OK"


def check_snowfall(snowfall_cm):
    t = THRESHOLDS["snowfall_cm"]
    if snowfall_cm > t:
        return SEVERITY_BLOCKED, f"Snowfall {snowfall_cm:.1f} cm exceeds limit ({t} cm) — flight grounded"
    elif snowfall_cm > 0:
        return SEVERITY_WARNING, f"Trace snowfall {snowfall_cm:.1f} cm — monitor closely"
    return SEVERITY_OK, f"Snowfall {snowfall_cm:.1f} cm — OK"


def check_visibility(visibility_m):
    t = THRESHOLDS["visibility_m"]
    if visibility_m < t:
        return SEVERITY_BLOCKED, f"Visibility {visibility_m:.0f} m below minimum ({t:.0f} m)"
    elif visibility_m < t * 1.5:
        return SEVERITY_WARNING, f"Visibility {visibility_m:.0f} m — reduced, proceed with caution"
    return SEVERITY_OK, f"Visibility {visibility_m:.0f} m — OK"


def check_temperature(temp_c):
    t_min = THRESHOLDS["temperature_min_c"]
    t_max = THRESHOLDS["temperature_max_c"]
    if temp_c < t_min:
        return SEVERITY_BLOCKED, f"Temperature {temp_c:.1f}°C below minimum ({t_min}°C) — battery failure risk"
    elif temp_c > t_max:
        return SEVERITY_BLOCKED, f"Temperature {temp_c:.1f}°C above maximum ({t_max}°C) — overheating risk"
    elif temp_c < t_min + 5:
        return SEVERITY_WARNING, f"Temperature {temp_c:.1f}°C — low, monitor battery performance"
    elif temp_c > t_max - 5:
        return SEVERITY_WARNING, f"Temperature {temp_c:.1f}°C — high, monitor motor temperature"
    return SEVERITY_OK, f"Temperature {temp_c:.1f}°C — OK"


def check_humidity(humidity_pct):
    t = THRESHOLDS["humidity_max_pct"]
    if humidity_pct > t:
        return SEVERITY_BLOCKED, f"Humidity {humidity_pct:.0f}% above maximum ({t:.0f}%) — electronics risk"
    elif humidity_pct > t - 5:
        return SEVERITY_WARNING, f"Humidity {humidity_pct:.0f}% — very high, monitor electronics"
    return SEVERITY_OK, f"Humidity {humidity_pct:.0f}% — OK"


def check_pressure(pressure_hpa):
    t = THRESHOLDS["pressure_min_hpa"]
    if pressure_hpa < t:
        return SEVERITY_BLOCKED, f"Pressure {pressure_hpa:.0f} hPa below minimum ({t:.0f} hPa) — insufficient lift"
    elif pressure_hpa < t + 20:
        return SEVERITY_WARNING, f"Pressure {pressure_hpa:.0f} hPa — low, reduced lift in highlands"
    return SEVERITY_OK, f"Pressure {pressure_hpa:.0f} hPa — OK"


def check_cloud_cover(cloud_cover_pct):
    t = THRESHOLDS["cloud_cover_high_pct"]
    if cloud_cover_pct > t:
        return SEVERITY_BLOCKED, f"High cloud cover {cloud_cover_pct:.0f}% above limit ({t:.0f}%) — icing risk"
    elif cloud_cover_pct > t * 0.8:
        return SEVERITY_WARNING, f"High cloud cover {cloud_cover_pct:.0f}% — elevated icing risk"
    return SEVERITY_OK, f"High cloud cover {cloud_cover_pct:.0f}% — OK"


def check_weather_code(code):
    desc = WMO_DESCRIPTIONS.get(code, f"Unknown code {code}")
    if code in BLOCKED_WEATHER_CODES:
        return SEVERITY_BLOCKED, f"Weather code {code} ({desc}) — flight grounded"
    elif code >= 61:   # any rain/snow/shower not in blocked set = warning
        return SEVERITY_WARNING, f"Weather code {code} ({desc}) — proceed with caution"
    return SEVERITY_OK, f"Weather code {code} ({desc}) — OK"


# ─────────────────────────────────────────────────────────────
#  Full location assessment
# ─────────────────────────────────────────────────────────────

def assess_location_weather(weather_tuple, from_coord=None, to_coord=None):
    """
    Run all 12 parameter checks on a single weather tuple.
    Returns a dict with:
        "coords"   : (lat, lon)
        "results"  : list of (parameter_name, severity, message)
        "overall"  : SEVERITY_OK | SEVERITY_WARNING | SEVERITY_BLOCKED
        "flyable"  : bool
    """
    w = _parse(weather_tuple)
    results = []

    # Wind speed
    results.append(("wind_speed",       *check_wind_speed(w["wind_speed"])))

    # Wind direction (requires bearing — only if from/to coords provided)
    if from_coord and to_coord:
        results.append(("wind_direction", *check_wind_direction(from_coord, to_coord, w["wind_direction"])))
    else:
        results.append(("wind_direction", SEVERITY_OK,
                        f"Wind direction {w['wind_direction']:.0f}° (bearing not available for check)"))

    # Precipitation parameters
    results.append(("precipitation",    *check_precipitation(w["precipitation"])))
    results.append(("rain",             *check_rain(w["rain"])))
    results.append(("showers",          *check_showers(w["showers"])))
    results.append(("snowfall",         *check_snowfall(w["snowfall"])))

    # Visibility
    results.append(("visibility",       *check_visibility(w["visibility"])))

    # Atmospheric
    results.append(("temperature",      *check_temperature(w["temperature"])))
    results.append(("humidity",         *check_humidity(w["humidity"])))
    results.append(("pressure_msl",     *check_pressure(w["pressure_msl"])))
    results.append(("cloud_cover_high", *check_cloud_cover(w["cloud_cover_high"])))

    # Weather code (holistic WMO condition)
    results.append(("weather_code",     *check_weather_code(w["weather_code"])))

    # Overall severity
    severities = [r[1] for r in results]
    if SEVERITY_BLOCKED in severities:
        overall = SEVERITY_BLOCKED
    elif SEVERITY_WARNING in severities:
        overall = SEVERITY_WARNING
    else:
        overall = SEVERITY_OK

    return {
        "coords"  : w["coords"],
        "results" : results,
        "overall" : overall,
        "flyable" : overall != SEVERITY_BLOCKED,
        "raw"     : w,
    }


# ─────────────────────────────────────────────────────────────
#  Route-level functions (called from main)
# ─────────────────────────────────────────────────────────────

def get_weather_for_locations(locations_with_elevation):
    """Fetch weather for a list of (coord, elevation) tuples."""
    latitudes  = [lat for (lat, lon), elev in locations_with_elevation]
    longitudes = [lon for (lat, lon), elev in locations_with_elevation]
    elevations = [elev for (lat, lon), elev in locations_with_elevation]
    return get_weather(latitudes, longitudes, elevations)


def check_weather(locations_with_weather, from_coord=None, to_coord=None, verbose=True):
    """
    Assess weather at every intermediate point along a route segment.
    Prints a full report and returns a summary dict.

    Parameters
    ----------
    locations_with_weather : list of weather tuples from get_weather()
    from_coord             : (lat, lon) of segment start — used for wind direction check
    to_coord               : (lat, lon) of segment end   — used for wind direction check
    verbose                : print detailed per-point report

    Returns
    -------
    {
        "total_points"     : int,
        "flyable_points"   : int,
        "warning_points"   : int,
        "blocked_points"   : int,
        "route_flyable"    : bool,
        "blocked_params"   : list of parameter names that caused blocks,
        "assessments"      : list of full assessment dicts per point,
    }
    """
    assessments     = []
    blocked_params  = set()
    flyable_count   = 0
    warning_count   = 0
    blocked_count   = 0

    for idx, w in enumerate(locations_with_weather):
        assessment = assess_location_weather(w, from_coord, to_coord)
        assessments.append(assessment)

        if assessment["overall"] == SEVERITY_BLOCKED:
            blocked_count += 1
            for param, severity, _ in assessment["results"]:
                if severity == SEVERITY_BLOCKED:
                    blocked_params.add(param)
        elif assessment["overall"] == SEVERITY_WARNING:
            warning_count += 1
        else:
            flyable_count += 1

    route_flyable = blocked_count == 0
    total = len(locations_with_weather)

    # ── Print report ──────────────────────────────────────────
    if verbose:
        print(f"\n{'='*65}")
        print(f"  WEATHER ASSESSMENT REPORT")
        print(f"  Points checked : {total}")
        print(f"{'='*65}")

        for idx, a in enumerate(assessments):
            status_icon = {"OK": "✅", "WARNING": "⚠️ ", "BLOCKED": "🚫"}[a["overall"]]
            print(f"\n  Point {idx+1:02d} {status_icon} {a['overall']}  @ {a['coords'][0]:.5f}, {a['coords'][1]:.5f}")

            if verbose:
                for param, severity, msg in a["results"]:
                    icon = {"OK": "  ✓", "WARNING": "  ⚠", "BLOCKED": "  ✗"}[severity]
                    if severity != SEVERITY_OK:   # only print non-OK lines unless full verbose
                        print(f"      {icon}  [{param:<20}]  {msg}")

        print(f"\n{'─'*65}")
        print(f"  Summary:")
        print(f"    ✅  Flyable  : {flyable_count}/{total} points")
        print(f"    ⚠️   Warning  : {warning_count}/{total} points")
        print(f"    🚫  Blocked  : {blocked_count}/{total} points")

        if route_flyable:
            if warning_count > 0:
                print(f"\n  ⚠️  ROUTE FLYABLE WITH CAUTION")
            else:
                print(f"\n  ✅  ROUTE CLEAR — All points flyable")
        else:
            print(f"\n  🚫  ROUTE BLOCKED")
            print(f"      Blocking parameters : {', '.join(sorted(blocked_params))}")

        print(f"{'='*65}\n")

    return {
        "total_points"   : total,
        "flyable_points" : flyable_count,
        "warning_points" : warning_count,
        "blocked_points" : blocked_count,
        "route_flyable"  : route_flyable,
        "blocked_params" : sorted(blocked_params),
        "assessments"    : assessments,
    }


# ─────────────────────────────────────────────────────────────
#  Legacy wind-only function (preserved for backwards compatibility)
# ─────────────────────────────────────────────────────────────

def wind_direction_check(from_coordinate, to_coordinate, wind_direction):
    """Original wind-direction-only check. Preserved for compatibility."""
    bearing_direction = bearing_from_coords(
        from_coordinate[0], from_coordinate[1],
        to_coordinate[0],   to_coordinate[1]
    )
    if wind_direction >= WIND_DIRECTION_THRESHOLD:
        wind_direction_min = wind_direction - WIND_DIRECTION_THRESHOLD
        wind_direction_max = wind_direction + WIND_DIRECTION_THRESHOLD
    else:
        wind_direction_min = wind_direction
        wind_direction_max = wind_direction + WIND_DIRECTION_THRESHOLD

    return wind_direction_min <= bearing_direction <= wind_direction_max
