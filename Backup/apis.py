import requests
from requests.exceptions import ConnectionError, ReadTimeout
import openmeteo_requests
import requests_cache
from retry_requests import retry
import time
import sys

RETRIES = 3

def get_elevation(latitude, longitude):
    for attempt in range(RETRIES):
        try:
            response = requests.get(
                url=f"https://api.open-meteo.com/v1/elevation?latitude={latitude}&longitude={longitude}",
                timeout=30,
            )
            return response.json()["elevation"][0]
        except (ConnectionError, ReadTimeout):
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
            else:
                raise

def get_weather(latitudes, longitudes, elevations):
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://api.open-meteo.com/v1/forecast"

    locations_with_weather = []
    for lat, lon, elev in zip(latitudes, longitudes, elevations):
        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elev,
            "current": ["wind_direction_180m", "temperature_180m", "relative_humidity_2m",
                        "wind_speed_180m", "precipitation", "rain", "showers", "snowfall",
                        "weather_code", "pressure_msl", "cloud_cover_high", "visibility"],
            "timezone": "Asia/Colombo"
        }
        response = openmeteo.weather_api(url, params=params)[0]  # single response
        current = response.Current()
        locations_with_weather.append((
            (lat, lon),
            elev,
            current.Variables(0).Value(),  # wind_direction_180m
            current.Variables(1).Value(),  # temperature_180m
            current.Variables(2).Value(),  # relative_humidity_2m
            current.Variables(3).Value(),  # wind_speed_180m
            current.Variables(4).Value(),  # precipitation
            current.Variables(5).Value(),  # rain
            current.Variables(6).Value(),  # showers
            current.Variables(7).Value(),  # snowfall
            current.Variables(8).Value(),  # weather_code
            current.Variables(9).Value(),  # pressure_msl
            current.Variables(10).Value(),  # cloud_cover_high
            current.Variables(11).Value(),  # visibility
        ))

    return locations_with_weather