import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry

def get_elevation(latitude, longitude):
    response = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={latitude}&longitude={longitude}")
    return response.json()["elevation"][0]

def get_weather(latitudes, longitudes, elevations):
    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "current": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature",
                    "precipitation_probability", "precipitation", "rain", "showers", "snowfall", "snow_depth",
                    "weather_code", "pressure_msl", "surface_pressure", "cloud_cover", "cloud_cover_low",
                    "cloud_cover_mid", "cloud_cover_high", "visibility", "evapotranspiration",
                    "et0_fao_evapotranspiration", "vapour_pressure_deficit", "wind_speed_10m", "wind_speed_80m",
                    "wind_speed_120m", "wind_speed_180m", "wind_direction_10m", "wind_direction_80m",
                    "wind_direction_120m", "wind_direction_180m", "wind_gusts_10m", "temperature_80m",
                    "temperature_120m", "temperature_180m"],
        "elevation": elevations,
        "timezone": "Asia/Colombo"
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process 3 locations
    for response in responses:
        print(f"\nCoordinates: {response.Latitude()}°N {response.Longitude()}°E")
        print(f"Elevation: {response.Elevation()} m asl")
        print(f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()}s")

        # Process current data. The order of variables needs to be the same as requested.
        current = response.Current()
        temperature_2m = current.Variables(0).Value()
        relative_humidity_2m = current.Variables(1).Value()
        dew_point_2m = current.Variables(2).Value()
        apparent_temperature = current.Variables(3).Value()
        precipitation_probability = current.Variables(4).Value()
        precipitation = current.Variables(5).Value()
        rain = current.Variables(6).Value()
        showers = current.Variables(7).Value()
        snowfall = current.Variables(8).Value()
        snow_depth = current.Variables(9).Value()
        code = current.Variables(10).Value()
        pressure_msl = current.Variables(11).Value()
        surface_pressure = current.Variables(12).Value()
        cloud_cover = current.Variables(13).Value()
        cloud_cover_low = current.Variables(14).Value()
        cloud_cover_mid = current.Variables(15).Value()
        cloud_cover_high = current.Variables(16).Value()
        visibility = current.Variables(17).Value()
        evapotranspiration = current.Variables(18).Value()
        et0_fao_evapotranspiration = current.Variables(19).Value()
        vapour_pressure_deficit = current.Variables(20).Value()
        wind_speed_10m = current.Variables(21).Value()
        wind_speed_80m = current.Variables(22).Value()
        wind_speed_120m = current.Variables(23).Value()
        wind_speed_180m = current.Variables(24).Value()
        wind_direction_10m = current.Variables(25).Value()
        wind_direction_80m = current.Variables(26).Value()
        wind_direction_120m = current.Variables(27).Value()
        wind_direction_180m = current.Variables(28).Value()
        wind_gusts_10m = current.Variables(29).Value()
        temperature_80m = current.Variables(30).Value()
        temperature_120m = current.Variables(31).Value()
        temperature_180m = current.Variables(32).Value()