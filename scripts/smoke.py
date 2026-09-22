"""Free container smoke test; requires a running stack and downloaded model."""

import json
import subprocess
from urllib.request import urlopen


def cli(*args):
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            "DISABLE_PAID_API=true",
            "-e",
            "OPENAI_API_KEY=",
            "api",
            "nexusrag",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def main():
    ready = cli("preflight", "--require-ready")
    assert ready["status"] == "ok"
    for mode in ("vector", "graph_vector"):
        result = cli(
            "ask",
            "Trace Frontend → Checkout → Shipping → Quote.",
            "--mode",
            mode,
            "--retrieval-only",
        )
        assert result["status"] == "completed" and result["evidence"]
        assert result["trace"]["calls"] == [] and not result["generation_requested"]
        if mode == "graph_vector":
            assert result["paths"] and not result["trace"]["errors"]
        with urlopen(
            f"http://127.0.0.1:58000/queries/{result['query_id']}", timeout=10
        ) as response:
            assert json.load(response)["query_id"] == result["query_id"]
    for url in (
        "http://127.0.0.1:58000/health",
        "http://127.0.0.1:58000/ready",
        "http://127.0.0.1:58000/documents",
        "http://127.0.0.1:58000/openapi.json",
        "http://127.0.0.1:58501/_stcore/health",
    ):
        with urlopen(url, timeout=10) as response:
            assert response.status == 200
    print(
        "PASS: preflight, both retrieval modes, graph provenance, query records, API and UI health; zero paid calls"
    )


if __name__ == "__main__":
    main()
