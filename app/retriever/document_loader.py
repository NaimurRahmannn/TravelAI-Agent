"""Loads and chunks the plain-text/markdown knowledge base under `data/`."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LoadedDocument:
    source: str
    text: str


def load_documents(knowledge_dir: str) -> list[LoadedDocument]:
    """Read every .md/.txt file directly inside `knowledge_dir`."""
    if not os.path.isdir(knowledge_dir):
        return []

    documents = []
    for filename in sorted(os.listdir(knowledge_dir)):
        if not filename.lower().endswith((".md", ".txt")):
            continue

        path = os.path.join(knowledge_dir, filename)
        if not os.path.isfile(path):
            continue

        with open(path, encoding="utf-8") as f:
            text = f.read()

        documents.append(LoadedDocument(source=filename, text=text))

    return documents


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries.

    First splits on blank lines (paragraphs). Paragraphs are then packed
    into chunks up to `chunk_size` characters; a paragraph longer than
    `chunk_size` on its own is hard-split with `overlap` characters of
    lookback so a mid-sentence cut doesn't lose context.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(paragraph, chunk_size, overlap))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]
