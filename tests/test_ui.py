from pathlib import Path
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


def test_ui_renders_all_three_views_without_credentials():
    response = httpx.Response(200, json={"status": "ready", "generation_configured": False})
    with patch("httpx.get", return_value=response):
        app = AppTest.from_file(Path("src/nexusrag/ui.py").resolve()).run()
        assert not app.exception
        assert app.title[0].value == "NexusRAG"
        assert "OPENAI_API_KEY" in app.warning[0].value
        app.sidebar.radio[0].set_value("Evidence and execution").run()
        assert not app.exception
        app.sidebar.radio[0].set_value("Benchmark results").run()
        assert not app.exception
