import hashlib
from pathlib import Path

from nexusrag.models import Manifest

ALLOWED_DOCUMENTS = {
    "architecture",
    "services",
    "frontend",
    "checkout",
    "cart",
    "kafka",
    "accounting",
    "fraud-detection",
    "shipping",
    "quote",
    "recommendation",
    "product-catalog",
}


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def load_corpus(root: Path) -> tuple[Manifest, dict[str, str]]:
    manifest = Manifest.model_validate_json((root / "manifest.json").read_text())
    ids = [d.document_id for d in manifest.documents]
    if len(ids) != 12 or set(ids) != ALLOWED_DOCUMENTS:
        raise ValueError("Manifest must contain exactly the twelve V1 documents")
    content = {}
    for doc in manifest.documents:
        path = (root / doc.path).resolve()
        if not path.is_relative_to(root.resolve()) or path.suffix != ".md":
            raise ValueError("Unsafe manifest path")
        expected = f"https://github.com/open-telemetry/opentelemetry.io/blob/{manifest.repository_commit}/{doc.repository_path}"
        if doc.source_url != expected:
            raise ValueError("Source URL does not identify the frozen commit")
        raw = path.read_bytes()
        if digest(raw) != doc.sha256:
            raise ValueError(f"Checksum mismatch: {doc.document_id}")
        content[doc.document_id] = raw.decode("utf-8")
    return manifest, content
