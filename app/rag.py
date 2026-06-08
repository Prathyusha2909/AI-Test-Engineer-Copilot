from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.domain import SourceReference


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "shall",
    "should",
    "that",
    "the",
    "to",
    "with",
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_./-]+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


@dataclass
class KnowledgeChunk:
    id: str
    title: str
    text: str
    term_counts: Counter[str]


class SimpleRAG:
    """Small local retriever used so the demo runs without external services."""

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks
        self.document_frequency = self._build_document_frequency(chunks)

    @classmethod
    def from_documents(cls, documents: dict[str, str]) -> "SimpleRAG":
        chunks: list[KnowledgeChunk] = []
        for title, text in documents.items():
            for index, chunk_text in enumerate(split_into_chunks(text), start=1):
                chunk_id = f"{slugify(title)}-{index}"
                chunks.append(
                    KnowledgeChunk(
                        id=chunk_id,
                        title=f"{title} #{index}",
                        text=chunk_text.strip(),
                        term_counts=Counter(tokenize(chunk_text)),
                    )
                )
        return cls(chunks)

    def search(self, query: str, limit: int = 3) -> list[SourceReference]:
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []

        scored: list[tuple[float, KnowledgeChunk]] = []
        total_docs = max(len(self.chunks), 1)

        for chunk in self.chunks:
            score = 0.0
            for term, query_count in query_terms.items():
                term_frequency = chunk.term_counts.get(term, 0)
                if not term_frequency:
                    continue
                inverse_doc_freq = math.log((1 + total_docs) / (1 + self.document_frequency.get(term, 0))) + 1
                score += query_count * term_frequency * inverse_doc_freq

            if score:
                normalized = score / math.sqrt(sum(value * value for value in chunk.term_counts.values()))
                scored.append((normalized, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SourceReference(
                title=chunk.title,
                snippet=compact(chunk.text),
                score=round(score, 3),
            )
            for score, chunk in scored[:limit]
        ]

    @staticmethod
    def _build_document_frequency(chunks: list[KnowledgeChunk]) -> Counter[str]:
        frequency: Counter[str] = Counter()
        for chunk in chunks:
            frequency.update(set(chunk.term_counts))
        return frequency


def split_into_chunks(text: str, target_size: int = 900) -> list[str]:
    sections = re.split(r"(?m)^#{1,4}\s+", text)
    paragraphs: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        paragraphs.extend(part.strip() for part in re.split(r"\n\s*\n", section) if part.strip())

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= target_size:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [text]


def compact(text: str, limit: int = 260) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return value or "document"
