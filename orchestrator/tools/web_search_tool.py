"""Web search tool using DuckDuckGo."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for trading research, strategies, and market information."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    }

    def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return json.dumps({
                "status": "ok",
                "query": query,
                "count": len(results),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                    for r in results
                ],
            })
        except ImportError:
            return json.dumps({"status": "error", "error": "ddgs package not installed. pip install ddgs"})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class WebReadTool(BaseTool):
    name = "read_url"
    description = "Fetch and read content from a URL."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max characters to return (default 5000)"},
        },
        "required": ["url"],
    }

    def execute(self, **kwargs: Any) -> str:
        import requests

        url = kwargs.get("url", "")
        max_chars = kwargs.get("max_chars", 5000)

        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "TradingVault/1.0"})
            resp.raise_for_status()
            text = resp.text[:max_chars]
            return json.dumps({"status": "ok", "url": url, "length": len(text), "content": text})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
