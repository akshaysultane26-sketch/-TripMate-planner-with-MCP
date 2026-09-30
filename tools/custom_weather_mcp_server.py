import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

mcp = FastMCP("custom-weather")


def _check_api_key() -> str | None:
    if not OPENWEATHER_API_KEY:
        return (
            "Weather API error: OPENWEATHER_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "OPENWEATHER_API_KEY=your_api_key_here"
        )
    return None


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Get the current weather conditions for a city."""
    key_error = _check_api_key()
    if key_error:
        return key_error

    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(CURRENT_WEATHER_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Weather API request failed: {e}"

    if str(data.get("cod")) != "200":
        return f"Weather API error: {data.get('message', 'Unknown error')} (city: {city})"

    weather_desc = data["weather"][0]["description"].capitalize()
    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]

    return (
        f"Current weather in {city}:\n"
        f"- Conditions: {weather_desc}\n"
        f"- Temperature: {temp}°C (feels like {feels_like}°C)\n"
        f"- Humidity: {humidity}%\n"
        f"- Wind speed: {wind_speed} m/s"
    )


@mcp.tool()
def get_forecast(city: str) -> str:
    """Get a 5-day / 3-hour interval weather forecast for a city, summarized by day."""
    key_error = _check_api_key()
    if key_error:
        return key_error

    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(FORECAST_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Weather API request failed: {e}"

    if str(data.get("cod")) != "200":
        return f"Weather API error: {data.get('message', 'Unknown error')} (city: {city})"

    # Group the 3-hour entries by date, keeping the midday reading as the
    # representative forecast for that day (simple, readable summary).
    daily = {}
    for entry in data.get("list", []):
        date, time = entry["dt_txt"].split(" ")
        if date not in daily or time == "12:00:00":
            daily[date] = entry

    lines = [f"5-day forecast for {city}:"]
    for date, entry in list(daily.items())[:5]:
        desc = entry["weather"][0]["description"].capitalize()
        temp = entry["main"]["temp"]
        lines.append(f"- {date}: {desc}, {temp}°C")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")