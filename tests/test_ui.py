from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest


def test_ui_renders_all_three_views_without_credentials():
    response = httpx.Response(200, json={"status": "ready", "generation_configured": False})
    with patch("httpx.get", return_value=response):
        app = AppTest.from_file(Path("src/nexusrag/ui.py").resolve()).run()
        assert not app.exception
        assert app.title[0].value == "NexusRAG"
        assert "Evidence search is ready" in app.info[0].value
        assert app.checkbox[0].disabled and not app.checkbox[0].value
        app.sidebar.radio[0].set_value("Evidence and execution").run()
        assert not app.exception
        app.sidebar.radio[0].set_value("Benchmark results").run()
        assert not app.exception


def query_response(mode, generate=False):
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "mode": mode,
            "generation_requested": generate,
            "answer": None,
            "evidence": [],
            "paths": [],
            "trace": {
                "latency_ms": {"total": 10},
                "calls": [],
                "estimated_cost_usd": 0,
                "fallbacks": [],
            },
        },
    )


@pytest.mark.parametrize("generation_configured", [False, True])
def test_ui_compares_evidence_without_generation_by_default(generation_configured):
    ready = httpx.Response(
        200, json={"status": "ready", "generation_configured": generation_configured}
    )
    with (
        patch("httpx.get", return_value=ready),
        patch(
            "httpx.post", side_effect=[query_response("vector"), query_response("graph_vector")]
        ) as post,
    ):
        app = AppTest.from_file(Path("src/nexusrag/ui.py").resolve()).run()
        app.text_area[0].set_value("What is Checkout?")
        app.radio[0].set_value("Compare").run()
        app.button[0].click().run()
        assert not app.exception
        assert post.call_count == 2
        assert [call.kwargs["json"]["mode"] for call in post.call_args_list] == [
            "vector",
            "graph_vector",
        ]
        assert all(call.kwargs["params"] == {"generate": "false"} for call in post.call_args_list)
        assert len(app.subheader) == 2
        assert any("no answer was generated" in info.value for info in app.info)


def test_ui_generation_requires_explicit_selection():
    ready = httpx.Response(200, json={"status": "ready", "generation_configured": True})
    with (
        patch("httpx.get", return_value=ready),
        patch("httpx.post", return_value=query_response("vector", generate=True)) as post,
    ):
        app = AppTest.from_file(Path("src/nexusrag/ui.py").resolve()).run()
        app.text_area[0].set_value("What is Checkout?")
        app.checkbox[0].check().run()
        assert app.button[0].label == "Find evidence and answer"
        app.button[0].click().run()
        assert not app.exception
        assert post.call_args.kwargs["params"] == {"generate": "true"}
