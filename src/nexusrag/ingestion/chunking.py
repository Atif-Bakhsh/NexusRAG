"""Markdown block-aware packing with exact line provenance and bounded line overlap."""

from collections.abc import Callable

import yaml
from markdown_it import MarkdownIt

from nexusrag.ingestion.corpus import digest
from nexusrag.models import Chunk, Document


def chunk_document(
    doc: Document,
    raw: str,
    corpus_version: str,
    count: Callable[[str], int],
    version: str = "markdown-lines-v1",
    target: int = 256,
    maximum: int = 320,
    overlap: int = 32,
) -> list[Chunk]:
    lines = raw.splitlines(keepends=True)
    offset = 0
    metadata: dict = {}
    if lines and lines[0].strip() == "---":
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if closing is None:
            raise ValueError("Unclosed frontmatter")
        metadata = yaml.safe_load("".join(lines[1:closing])) or {}
        offset = closing + 1
    title = str(metadata.get("title", doc.document_id))
    body = "".join(lines[offset:])
    tokens = MarkdownIt("commonmark").enable("table").parse(body)
    blocks = []
    headings: list[tuple[int, str]] = []
    for token in tokens:
        if token.level != 0 or token.map is None or token.type.endswith("_close"):
            continue
        start, end = token.map
        start, end = start + offset, end + offset
        if token.type == "heading_open":
            level = int(token.tag[1])
            label = lines[start].strip().lstrip("#").strip()
            headings = [(n, h) for n, h in headings if n < level] + [(level, label)]
        section = " / ".join(h for _, h in headings) or title
        blocks.append((start, end, section))
    chunks: list[Chunk] = []

    def emit(start: int, end: int, section: str):
        text = "".join(lines[start:end])
        if not text.strip():
            return
        hash_ = digest(text)
        chunks.append(
            Chunk(
                chunk_id=digest(f"{corpus_version}:{doc.sha256}:{version}:{start}:{end}:{hash_}")[
                    :32
                ],
                corpus_version=corpus_version,
                document_id=doc.document_id,
                title=title,
                source_url=doc.source_url,
                section=section,
                line_start=start + 1,
                line_end=end,
                text=text,
                content_hash=hash_,
                document_date=str(metadata["date"]) if "date" in metadata else None,
            )
        )

    pending = None
    for start, end, section in blocks:
        prefix = f"{title} / {section}\n"
        if pending:
            a, b, sec = pending
            if sec == section and count(prefix + "".join(lines[a:end])) <= min(target, maximum):
                pending = (a, end, sec)
                continue
            emit(a, b, sec)
            pending = None
        if count(prefix + "".join(lines[start:end])) <= maximum:
            pending = (start, end, section)
            continue
        # Split oversized code, lists, tables and prose on source lines only.
        cursor = start
        while cursor < end:
            stop = cursor
            while stop < end and count(prefix + "".join(lines[cursor : stop + 1])) <= maximum:
                stop += 1
                if count(prefix + "".join(lines[cursor:stop])) >= target:
                    break
            if stop == cursor:
                raise ValueError(
                    f"Single source line exceeds token limit: {doc.document_id}:{cursor + 1}"
                )
            emit(cursor, stop, section)
            if stop == end:
                break
            next_start = stop
            while (
                next_start > cursor + 1 and count("".join(lines[next_start - 1 : stop])) <= overlap
            ):
                next_start -= 1
            cursor = next_start
    if pending:
        emit(*pending)
    return chunks
