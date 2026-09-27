from ddgs import DDGS


def duckduckgo_search(query, max_results=3):
    results_list = []

    with DDGS() as ddgs:
        response = ddgs.text(query, max_results=max_results)

        for i, r in enumerate(response, 1):
            title = r.get("title", "Unknown")
            url = r.get("href", "")
            snippet = r.get("body", "").strip()

            if len(snippet) > 150:
                snippet = snippet[:150].rsplit(" ", 1)[0] + "..."

            results_list.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

    return "\n\n".join(results_list)