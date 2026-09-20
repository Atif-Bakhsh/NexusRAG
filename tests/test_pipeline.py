from pathlib import Path
from types import SimpleNamespace

import pytest

from nexusrag.config import Settings
from nexusrag.ingestion.corpus import load_corpus
from nexusrag.ingestion.pipeline import ingest


def test_failed_ingestion_never_marks_new_version_ready(tmp_path, monkeypatch, make_chunk):
    manifest, _ = load_corpus(Path("corpus"))
    manifest.corpus_version = "new-v"
    chunk = make_chunk(version="new-v")
    events = []

    class Repo:
        def is_ready(self, v):
            return False

        def stage(self, *args):
            events.append("staged")

        def store_chunks(self, *args):
            events.append("embedded")

        def chunks(self, *args):
            return [chunk]

        def mark_ready(self, *args):
            events.append("ready")

    class Graph:
        def close(self):
            events.append("closed")

        def import_assertions(self, *args):
            raise RuntimeError("import failed")

    monkeypatch.setattr("nexusrag.ingestion.pipeline.Repository", lambda s: Repo())
    monkeypatch.setattr("nexusrag.ingestion.pipeline.GraphStore", lambda s: Graph())
    monkeypatch.setattr(
        "nexusrag.ingestion.pipeline.Embedder",
        lambda s: SimpleNamespace(passages=lambda texts: [[1] * 384]),
    )
    monkeypatch.setattr("nexusrag.ingestion.pipeline.prepare", lambda *args: (manifest, [chunk]))
    artifact = tmp_path / "empty.jsonl"
    artifact.write_text("")
    with pytest.raises(RuntimeError, match="import failed"):
        ingest(Settings(artifact_dir=tmp_path), artifact)
    assert events == ["staged", "embedded", "closed"]


def test_ready_ingestion_is_noop(tmp_path, monkeypatch):
    manifest, _ = load_corpus(Path("corpus"))
    monkeypatch.setattr(
        "nexusrag.ingestion.pipeline.Repository", lambda s: SimpleNamespace(is_ready=lambda v: True)
    )
    monkeypatch.setattr(
        "nexusrag.ingestion.pipeline.GraphStore",
        lambda s: SimpleNamespace(ready=lambda v: True, close=lambda: None),
    )
    monkeypatch.setattr("nexusrag.ingestion.pipeline.Embedder", lambda s: None)
    monkeypatch.setattr("nexusrag.ingestion.pipeline.prepare", lambda *args: (manifest, []))
    assert ingest(Settings(artifact_dir=tmp_path))["status"] == "already_ready"
