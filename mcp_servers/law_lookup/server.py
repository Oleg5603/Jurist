import json
import os

from mcp.server.fastmcp import FastMCP

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "law_index.json")

with open(_INDEX_PATH, encoding="utf-8") as f:
    _LAW_INDEX: dict[str, dict[str, str]] = json.load(f)


def lookup_article(law: str, number: str) -> dict:
    title = _LAW_INDEX.get(law, {}).get(number)
    return {"exists": title is not None, "title": title}


mcp = FastMCP("jurist-law-lookup")


@mcp.tool()
def lookup_article_tool(law: str, number: str) -> dict:
    """Check whether a statute article exists in the offline index."""
    return lookup_article(law, number)


if __name__ == "__main__":
    mcp.run()
