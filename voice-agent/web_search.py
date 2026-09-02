"""
Web search for the voice agent, via Ollama's hosted search API.

Shaped for SPEECH, which is the whole design constraint here. The API returns
around 3 KB of page text per result; handing that to the model produces a long,
list-shaped answer that is miserable to listen to and slow to generate. So
results are trimmed hard and the model is told to summarise rather than read.

Docs: https://docs.ollama.com/capabilities/web-search
"""

import asyncio
import json
import os
import ssl
import urllib.error
import urllib.request

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:                       # pragma: no cover
    _SSL = ssl.create_default_context()

SEARCH_URL = "https://ollama.com/api/web_search"
FETCH_URL = "https://ollama.com/api/web_fetch"

# Three results, ~600 characters each: enough to answer a spoken question,
# small enough that the model does not start reciting a list. The API's default
# is 5 results at full length, which is far too much for a voice turn.
MAX_RESULTS = 3
MAX_CHARS_PER_RESULT = 600
TIMEOUT_S = 20.0


class SearchError(RuntimeError):
    pass


def _post(url: str, payload: dict) -> dict:
    key = os.environ.get("OLLAMA_API_KEY", "")
    if not key:
        raise SearchError("OLLAMA_API_KEY is not set")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SearchError(f"search returned HTTP {e.code}") from e
    except Exception as e:                # network, DNS, timeout
        raise SearchError(str(e)) from e


def _condense(results: list[dict], max_results: int, max_chars: int) -> str:
    """Flatten results into something short enough to speak from."""
    out = []
    for i, r in enumerate(results[:max_results], 1):
        title = (r.get("title") or "").strip()
        content = " ".join((r.get("content") or "").split())
        if len(content) > max_chars:
            content = content[:max_chars].rsplit(" ", 1)[0] + "…"
        out.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(out) if out else "No results."


async def search(query: str, max_results: int = MAX_RESULTS) -> str:
    """Run a web search and return condensed text. Never raises."""
    try:
        # urllib is blocking; a voice session's event loop must not stall.
        data = await asyncio.to_thread(
            _post, SEARCH_URL,
            {"query": query, "max_results": max(1, min(int(max_results), 10))},
        )
    except SearchError as e:
        return f"The search could not be completed: {e}"
    return _condense(data.get("results", []), max_results, MAX_CHARS_PER_RESULT)
