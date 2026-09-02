import asyncio

import pytest

import web_search


def test_condense_trims_long_content():
    long = "word " * 500
    out = web_search._condense([{"title": "T", "content": long}], 3, 100)
    assert len(out) < 200
    assert out.endswith("…")


def test_condense_numbers_results():
    out = web_search._condense(
        [{"title": "A", "content": "a"}, {"title": "B", "content": "b"}], 3, 600)
    assert "[1] A" in out and "[2] B" in out


def test_condense_respects_max_results():
    rs = [{"title": f"T{i}", "content": "x"} for i in range(9)]
    assert "[4]" not in web_search._condense(rs, 3, 600)


def test_condense_collapses_whitespace():
    out = web_search._condense([{"title": "T", "content": "a\n\n  b\tc"}], 3, 600)
    assert "a b c" in out


def test_condense_handles_empty():
    assert web_search._condense([], 3, 600) == "No results."


def test_condense_tolerates_missing_fields():
    out = web_search._condense([{}], 3, 600)
    assert "[1]" in out


def test_search_reports_failure_instead_of_raising(monkeypatch):
    def boom(*a, **k):
        raise web_search.SearchError("no key")
    monkeypatch.setattr(web_search, "_post", boom)
    out = asyncio.run(web_search.search("anything"))
    assert "could not be completed" in out
    assert "no key" in out


def test_search_clamps_max_results(monkeypatch):
    seen = {}
    def fake(url, payload):
        seen.update(payload)
        return {"results": []}
    monkeypatch.setattr(web_search, "_post", fake)
    asyncio.run(web_search.search("q", max_results=99))
    assert seen["max_results"] == 10
    asyncio.run(web_search.search("q", max_results=0))
    assert seen["max_results"] == 1
