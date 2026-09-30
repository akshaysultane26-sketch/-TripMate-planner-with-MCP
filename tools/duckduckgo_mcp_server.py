from mcp.server.fastmcp import FastMCP
from ddgs import DDGS

# Local MCP server (stdio transport) exposing a DuckDuckGo search tool.
# This replaces Tavily's hosted remote MCP endpoint from the tutor's code.
mcp = FastMCP("duckduckgo-search")


@mcp.tool()
def duckduckgo_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return the top results as text."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(f"{r['title']}\n{r['href']}\n{r['body']}")

    return "\n\n".join(results) if results else "No results found."


if __name__ == "__main__":
    # stdio transport: the client will spawn this script as a subprocess
    # and talk to it over stdin/stdout — no network/SSL setup needed.
    mcp.run(transport="stdio")