import os
import sys
from pathlib import Path

import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq


# ==========================================
# Environment configuration
# ==========================================

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


# Resolve paths relative to this file (tools/), not the current working
# directory, so this works no matter where uvicorn/app.py is launched from.
PROJECT_DIR = Path(__file__).resolve().parent
DUCKDUCKGO_SERVER_PATH = PROJECT_DIR / "duckduckgo_mcp_server.py"
WEATHER_SERVER_PATH = PROJECT_DIR / "custom_weather_mcp_server.py"


# Preserve the full environment (PATH, etc.) when spawning local stdio
# MCP servers as subprocesses, and inject the API key each one needs.
WEATHER_ENV = os.environ.copy()
WEATHER_ENV["OPENWEATHER_API_KEY"] = OPENWEATHER_API_KEY or ""

# NOTE: AviationStack is NOT run through MCP. tools/flight_tool.py already
# calls the AviationStack REST API directly with full route-parsing logic
# (city/country -> IATA, "from X to Y" extraction) that the generic
# aviationstack-mcp tool wrapper doesn't replicate. flight_agent in
# backend.py imports search_flights from tools.flight_tool directly.


# ==========================================
# LLM
# ==========================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY
)


# ==========================================
# MCP client configuration
# ==========================================

client = MultiServerMCPClient(
    {
        "duckduckgo": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(DUCKDUCKGO_SERVER_PATH)],
        },

        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(WEATHER_SERVER_PATH)],
            "env": WEATHER_ENV
        }
    }
)


# ==========================================
# Diagnostic function
# ==========================================

async def get_all_tools():
    """
    Load each MCP server separately and print its tools.

    A broken server won't prevent the other working servers
    from loading. Run this directly to discover exact tool
    names/args before wiring a new server into backend.py.
    """

    all_tools = []

    for server_name in (
        "duckduckgo",
        "weather",
    ):
        try:
            tools = await client.get_tools(
                server_name=server_name
            )

            all_tools.extend(tools)

            print(f"\nAvailable tools from {server_name} MCP:\n")

            for tool in tools:
                print(tool.name)

        except Exception as error:
            print(f"\nCould not connect to {server_name} MCP:\n{error}\n")

    return all_tools


# ==========================================
# DuckDuckGo MCP tool
# ==========================================

search_tool = None


async def initialize_mcp():
    """Initialize the DuckDuckGo MCP tool (cached after the first call)."""

    global search_tool

    if search_tool is not None:
        return

    tools = await client.get_tools(server_name="duckduckgo")

    tools_by_name = {tool.name: tool for tool in tools}

    search_tool = tools_by_name.get("duckduckgo_search")

    if search_tool is None:
        available_tools = ", ".join(tools_by_name.keys())
        raise RuntimeError(
            "DuckDuckGo MCP connected, but the 'duckduckgo_search' tool "
            f"was not found. Available tools: {available_tools or 'none'}"
        )


async def duckduckgo_mcp_search(query: str):
    await initialize_mcp()
    result = await search_tool.ainvoke({"query": query})
    return result


# ==========================================
# Weather MCP tools
# ==========================================

weather_tool = None
forecast_tool = None


async def initialize_weather_tools():
    global weather_tool
    global forecast_tool

    if weather_tool is not None and forecast_tool is not None:
        return

    if not WEATHER_SERVER_PATH.exists():
        raise FileNotFoundError(
            f"Weather MCP server file was not found: {WEATHER_SERVER_PATH}"
        )

    # Load only weather — DuckDuckGo will not be re-initialized here.
    tools = await client.get_tools(server_name="weather")

    tools_by_name = {tool.name: tool for tool in tools}

    weather_tool = tools_by_name.get("get_current_weather")
    forecast_tool = tools_by_name.get("get_forecast")

    missing_tools = []
    if weather_tool is None:
        missing_tools.append("get_current_weather")
    if forecast_tool is None:
        missing_tools.append("get_forecast")

    if missing_tools:
        available_tools = ", ".join(tools_by_name.keys())
        raise RuntimeError(
            f"Missing Weather MCP tools: {', '.join(missing_tools)}. "
            f"Available tools: {available_tools or 'none'}"
        )


async def weather_mcp_search(city: str):
    await initialize_weather_tools()
    result = await weather_tool.ainvoke({"city": city})
    return result


async def forecast_mcp_search(city: str):
    await initialize_weather_tools()
    result = await forecast_tool.ainvoke({"city": city})
    return result


# ==========================================
# Destination extractor
# ==========================================

def extract_destination(query: str):
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = llm.invoke(prompt)
    return response.content.strip()