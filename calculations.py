import math
import numpy as np
import random
from variables import NUMBER_OF_POINTS_CONSTANT

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371.0  # km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int((R * c) * 1000)  # in meters

def calculate_coordinates(departing_coordinates, arriving_coordinates, routing_distance):
    # calculate gradient of the straight line between the two points
    gradient = (departing_coordinates[1] - arriving_coordinates[1]) / (
                departing_coordinates[0] - arriving_coordinates[0])
    intersect = (departing_coordinates[1] - gradient * departing_coordinates[0])
    number_of_points = calculate_number_of_points(departing_coordinates, arriving_coordinates, routing_distance)
    # create points (threshold) between departing and arriving coordinates that are on the straight line
    points_x = np.linspace(departing_coordinates[0], arriving_coordinates[0], number_of_points).tolist()
    points_y = list(map(lambda x: (gradient * x) + intersect, points_x))
    return list(zip(points_x, points_y))

def calculate_number_of_points(departing_coordinates, arriving_coordinate, routing_distance):
    distance = haversine_m(departing_coordinates[0], departing_coordinates[1], arriving_coordinate[0], arriving_coordinate[1])
    percentage = (distance / routing_distance) * 100
    return int(percentage*NUMBER_OF_POINTS_CONSTANT)

def reverse_harvesine(lat_deg, lon_deg, distance, bearing_deg):
    """
    Compute destination point from start point, distance, and bearing
    using a spherical Earth model.

    Parameters
    ----------
    lat_deg : float
        Start latitude in degrees.
    lon_deg : float
        Start longitude in degrees.
    distance : float
        Distance to travel (same units as `radius`).
    bearing_deg : float
        Bearing clockwise from true north, in degrees.
    radius : float, optional
        Sphere radius (default is mean Earth radius in meters).

    Returns
    -------
    (lat2_deg, lon2_deg) : tuple of float
        Destination latitude and longitude in degrees.
    """
    # Convert to radians
    lat1 = math.radians(lat_deg)
    lon1 = math.radians(lon_deg)
    bearing = math.radians(bearing_deg)

    # Angular distance
    delta = distance / 6371000.0

    # Destination latitude
    lat2 = math.asin(
        math.sin(lat1) * math.cos(delta)
        + math.cos(lat1) * math.sin(delta) * math.cos(bearing)
    )

    # Destination longitude
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )

    # Convert back to degrees
    lat2_deg = math.degrees(lat2)
    lon2_deg = math.degrees(lon2)

    # Normalize longitude to [-180, 180)
    lon2_deg = (lon2_deg + 540) % 360 - 180

    return lat2_deg, lon2_deg

def bearing_from_coords(lat1, lon1, lat2, lon2):
    """
    Bearing from point (lat1, lon1) to (lat2, lon2), in degrees.
    Angles are in decimal degrees, result is 0–360° clockwise from north.
    """
    # convert to radians
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    λ1 = math.radians(lon1)
    λ2 = math.radians(lon2)

    dλ = λ2 - λ1

    x = math.sin(dλ) * math.cos(φ2)
    y = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(dλ)

    θ = math.atan2(x, y)  # bearing in radians (−π, +π]
    brng = math.degrees(θ)  # convert to degrees
    brng = (brng + 360) % 360  # normalize to 0–360

    return brng

def random_location_around(lat, lng, radius_m):
    """
    Generate a uniformly distributed random point within a circle
    of radius_m meters around (lat, lng).
    """
    # Earth's radius in meters
    R = 6_371_000

    # Convert radius from meters to radians
    radius_rad = radius_m / R

    # Random angle (bearing) in radians
    angle = random.uniform(0, 2 * math.pi)

    # Random distance — sqrt ensures UNIFORM distribution within the circle
    # (without sqrt, points cluster near the center)
    distance = radius_rad * math.sqrt(random.uniform(0, 1))

    lat1 = math.radians(lat)
    lng1 = math.radians(lng)

    # Spherical offset calculation
    new_lat = math.asin(
        math.sin(lat1) * math.cos(distance) +
        math.cos(lat1) * math.sin(distance) * math.cos(angle)
    )
    new_lng = lng1 + math.atan2(
        math.sin(angle) * math.sin(distance) * math.cos(lat1),
        math.cos(distance) - math.sin(lat1) * math.sin(new_lat)
    )

    return math.degrees(new_lat), math.degrees(new_lng)