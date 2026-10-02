import math
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str
    equipment_type: str
    title: str
    content: str
    score: float = 0.0


def tokenize(text: str) -> list[str]:
    """Simple deterministic lowercase alphanumeric tokenization."""
    return [t for t in re.split(r"\W+", text.lower()) if t]


class Retriever:
    """
    Deterministic BM25 knowledge retrieval engine.
    Uses standard library only, completely independent of AI/LLMs.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[Chunk] = []
        self.doc_freqs: Counter[str] = Counter()
        self.doc_lens: list[int] = []
        self.avgdl: float = 0.0
        self.n_docs: int = 0
        self.doc_tokens: list[list[str]] = []

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add parsed markdown chunks and recompute DF/IDF statistics."""
        self.chunks.extend(chunks)
        self.n_docs = len(self.chunks)

        total_len = 0
        for chunk in chunks:
            tokens = tokenize(chunk.title + " " + chunk.content)
            self.doc_tokens.append(tokens)
            self.doc_lens.append(len(tokens))
            total_len += len(tokens)

            # Document frequency counts unique terms per document
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1

        if self.n_docs > 0:
            self.avgdl = total_len / self.n_docs

    def _idf(self, term: str) -> float:
        n = self.doc_freqs.get(term, 0)
        # BM25 IDF formulation
        return math.log(1.0 + (self.n_docs - n + 0.5) / (n + 0.5))

    def search(
        self, query: str, equipment_type: str | None = None, limit: int = 5
    ) -> list[Chunk]:
        """
        Rank chunks using BM25.
        Deterministic scoring and ordering.
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scored_chunks = []
        for i, chunk in enumerate(self.chunks):
            # Deterministic filtering
            if equipment_type and chunk.equipment_type.lower() != equipment_type.lower():
                continue

            score = 0.0
            doc_len = self.doc_lens[i]
            tokens = self.doc_tokens[i]
            term_counts = Counter(tokens)

            for q in query_tokens:
                if q not in term_counts:
                    continue
                f = term_counts[q]
                idf = self._idf(q)
                numerator = f * (self.k1 + 1)
                denominator = f + self.k1 * (
                    1 - self.b + self.b * (doc_len / self.avgdl) if self.avgdl else 1
                )
                score += idf * (numerator / denominator)

            if score > 0:
                result_chunk = chunk.model_copy()
                result_chunk.score = score
                scored_chunks.append(result_chunk)

        # Sort by score (descending), then stable chunk_id (ascending) to guarantee determinism
        scored_chunks.sort(key=lambda x: (-x.score, x.chunk_id))
        return scored_chunks[:limit]


def parse_markdown_manual(file_path: Path, equipment_type: str) -> list[Chunk]:
    """Parse a markdown manual into deterministic chunks by heading."""
    if not file_path.exists():
        return []

    text = file_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    chunks = []
    current_title = "General"
    current_content: list[str] = []

    def save_chunk() -> None:
        if current_content:
            content_str = "\n".join(current_content).strip()
            if content_str:
                # Stable deterministic ID
                safe_title = re.sub(r"[^a-z0-9]+", "-", current_title.lower()).strip("-")
                chunk_id = f"{equipment_type}-{safe_title}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        equipment_type=equipment_type,
                        title=current_title,
                        content=content_str,
                    )
                )

    for line in lines:
        if line.startswith("#"):
            save_chunk()
            current_title = line.lstrip("#").strip()
            current_content = []
        else:
            current_content.append(line)

    save_chunk()
    return chunks


def load_knowledge_base(kb_dir: Path) -> Retriever:
    """Load all markdown manuals from a directory into a Retriever instance."""
    retriever = Retriever()
    all_chunks = []
    
    if kb_dir.exists() and kb_dir.is_dir():
        # sort explicitly for deterministic loading order
        for md_file in sorted(kb_dir.glob("*.md")):
            eq_type = md_file.stem
            chunks = parse_markdown_manual(md_file, eq_type)
            all_chunks.extend(chunks)

    retriever.add_chunks(all_chunks)
    return retriever
