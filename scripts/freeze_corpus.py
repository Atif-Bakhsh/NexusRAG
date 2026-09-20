"""Download exactly the V1 allowlist from a reviewed commit; never crawl links."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

SHA = "a471a5d079a2c4aa02283f606babf339acf4ff48"
FILES = {"architecture": "architecture.md", "services": "services/_index.md"}
FILES.update(
    {
        name: f"services/{name}.md"
        for name in [
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
        ]
    }
)
FILES["cart"] = "services/cart/index.md"
root = Path(__file__).resolve().parents[1] / "corpus"
documents = []
for name, relative in FILES.items():
    remote = f"content/en/docs/demo/{relative}"
    url = f"https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/{SHA}/{remote}"
    with urlopen(url, timeout=35) as response:
        content = response.read()
    path = f"docs/{name}.md"
    (root / path).write_bytes(content)
    documents.append(
        dict(
            document_id=name,
            path=path,
            repository_path=remote,
            source_url=f"https://github.com/open-telemetry/opentelemetry.io/blob/{SHA}/{remote}",
            sha256=hashlib.sha256(content).hexdigest(),
        )
    )
manifest = dict(
    corpus_version=f"astronomy-{SHA[:12]}",
    repository_commit=SHA,
    repository="https://github.com/open-telemetry/opentelemetry.io",
    license="CC-BY-4.0",
    attribution="OpenTelemetry Authors",
    modification_notice="Markdown files retained verbatim; derived chunks and labels are NexusRAG transformations.",
    documents=documents,
)
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
with urlopen(
    f"https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/{SHA}/LICENSE", timeout=35
) as response:
    (root / "UPSTREAM-LICENSE").write_bytes(response.read())
print(f"Frozen {len(documents)} documents at {SHA}")
