"""Document extraction, chunking, embedding, and Qdrant/PostgreSQL indexing."""

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
import psycopg
from pypdf import PdfReader
from qdrant_client import QdrantClient, models

from ai_template_python.data_foundation.synthetic import SYNTHETIC_TENANT_ID

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 768
COLLECTION_BY_TYPE = {
    "contract": "procurement_contracts",
    "policy": "procurement_policies",
    "supplier_profile": "supplier_profiles",
    "market_report": "market_reports",
}


@dataclass(frozen=True, slots=True)
class DocumentSource:
    document_id: str
    document_type: str
    title: str
    path: Path
    source_name: str
    source_version: str
    content_sha256: str
    supplier_id: str | None = None
    tenant_id: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_synthetic: bool = False
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    point_id: UUID
    chunk_index: int
    content: str
    content_sha256: str
    collection_name: str


class EmbeddingProvider(Protocol):
    dimensions: int
    model_name: str

    def embed_document(self, *, title: str, text: str) -> list[float]: ...

    def embed_query(self, query: str) -> list[float]: ...


class GeminiEmbeddingProvider:
    """Gemini embedding REST client using retrieval-specific query/document prompts."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("GOOGLE_API_KEY is required to create document embeddings")
        if not 128 <= dimensions <= 3072:
            raise ValueError("Gemini embedding dimensions must be between 128 and 3072")
        self.dimensions = dimensions
        self.model_name = model_name
        self._client = client or httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            headers={"x-goog-api-key": api_key.strip()},
            timeout=httpx.Timeout(45.0, connect=5.0),
        )

    def _embed(self, text: str) -> list[float]:
        response = self._client.post(
            f"/models/{self.model_name}:embedContent",
            json={
                "model": f"models/{self.model_name}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self.dimensions,
            },
        )
        response.raise_for_status()
        payload = response.json()
        values = payload.get("embedding", {}).get("values")
        if not isinstance(values, list) or len(values) != self.dimensions:
            raise ValueError("Gemini returned an embedding with an unexpected dimension")
        vector = [float(value) for value in values]
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Gemini returned a non-finite embedding value")
        return vector

    def embed_document(self, *, title: str, text: str) -> list[float]:
        return self._embed(f"task: search result | title: {title} | text: {text}")

    def embed_query(self, query: str) -> list[float]:
        return self._embed(f"task: search result | query: {query}")


def load_document_manifest(manifest_path: str | Path) -> list[DocumentSource]:
    """Load and verify document metadata and content hashes from a JSON manifest."""
    manifest_file = Path(manifest_path).resolve()
    records = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Document manifest must be a JSON array")
    sources: list[DocumentSource] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Document manifest entries must be JSON objects")
        relative_path = Path(str(record["path"]))
        source_path = (manifest_file.parent / relative_path).resolve()
        if not source_path.is_relative_to(manifest_file.parent):
            raise ValueError("Document manifest path escapes its directory")
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        content_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if content_sha256 != record.get("content_sha256"):
            raise ValueError(f"Document content hash does not match manifest: {relative_path}")
        sources.append(
            DocumentSource(
                document_id=str(record["document_id"]),
                document_type=str(record["document_type"]),
                title=str(record["title"]),
                path=source_path,
                source_name=str(record["source_name"]),
                source_version=str(record["source_version"]),
                content_sha256=content_sha256,
                supplier_id=record.get("supplier_id"),
                tenant_id=SYNTHETIC_TENANT_ID if record.get("is_synthetic") else None,
                effective_from=(
                    date.fromisoformat(record["effective_from"])
                    if record.get("effective_from")
                    else None
                ),
                effective_to=(
                    date.fromisoformat(record["effective_to"])
                    if record.get("effective_to")
                    else None
                ),
                is_synthetic=bool(record.get("is_synthetic", False)),
            )
        )
    return sources


def world_bank_pdf_sources(data_dir: str | Path) -> list[DocumentSource]:
    """Create provenance records for the supplied World Bank commodity PDFs."""
    root = Path(data_dir).resolve()
    sources: list[DocumentSource] = []
    for path in sorted(root.glob("world-bank-commodities-price-*.pdf")):
        content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        title = f"World Bank commodity price report {path.stem.rsplit('-', 1)[-1]}"
        sources.append(
            DocumentSource(
                document_id=f"WB-COMMODITY-{path.stem.rsplit('-', 1)[-1]}",
                document_type="market_report",
                title=title,
                path=path,
                source_name="world_bank_commodity_report",
                source_version=content_sha256,
                content_sha256=content_sha256,
                source_url="https://www.worldbank.org/en/research/commodity-markets",
            )
        )
    return sources


def extract_document_text(path: str | Path) -> str:
    source_path = Path(path)
    if source_path.suffix.casefold() == ".pdf":
        pages = [page.extract_text() or "" for page in PdfReader(source_path).pages]
        text = "\n\n".join(f"Page {index + 1}\n{page}" for index, page in enumerate(pages))
    elif source_path.suffix.casefold() in {".md", ".txt"}:
        text = source_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported document format: {source_path.suffix}")
    if not text.strip():
        raise ValueError(f"Document contains no extractable text: {source_path.name}")
    return text


def chunk_text(text: str, *, words_per_chunk: int = 300, overlap_words: int = 40) -> list[str]:
    if words_per_chunk < 1 or not 0 <= overlap_words < words_per_chunk:
        raise ValueError("chunk sizes must satisfy 0 <= overlap_words < words_per_chunk")
    words = text.split()
    if not words:
        return []
    step = words_per_chunk - overlap_words
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + words_per_chunk, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


class QdrantDocumentIndexer:
    def __init__(self, client: QdrantClient, embeddings: EmbeddingProvider) -> None:
        self.client = client
        self.embeddings = embeddings

    def ensure_collections(self) -> None:
        for collection_name in COLLECTION_BY_TYPE.values():
            if not self.client.collection_exists(collection_name):
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self.embeddings.dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )

    def index_document(
        self,
        source: DocumentSource,
        content: str,
        *,
        words_per_chunk: int = 300,
        overlap_words: int = 40,
    ) -> list[IndexedChunk]:
        try:
            collection_name = COLLECTION_BY_TYPE[source.document_type]
        except KeyError as error:
            raise ValueError(f"Unsupported document type: {source.document_type}") from error
        parts = chunk_text(content, words_per_chunk=words_per_chunk, overlap_words=overlap_words)
        if not parts:
            raise ValueError("Cannot index an empty document")
        self.ensure_collections()
        indexed_chunks: list[IndexedChunk] = []
        points: list[models.PointStruct] = []
        for index, part in enumerate(parts):
            chunk_sha256 = hashlib.sha256(part.encode("utf-8")).hexdigest()
            point_id = uuid5(
                NAMESPACE_URL,
                f"{source.document_id}:{index}:{chunk_sha256}:{self.embeddings.model_name}",
            )
            indexed_chunks.append(
                IndexedChunk(
                    point_id=point_id,
                    chunk_index=index,
                    content=part,
                    content_sha256=chunk_sha256,
                    collection_name=collection_name,
                )
            )
            points.append(
                models.PointStruct(
                    id=str(point_id),
                    vector=self.embeddings.embed_document(title=source.title, text=part),
                    payload={
                        "document_id": source.document_id,
                        "document_type": source.document_type,
                        "supplier_id": source.supplier_id,
                        "tenant_id": source.tenant_id,
                        "is_public": source.tenant_id is None,
                        "is_synthetic": source.is_synthetic,
                        "source_name": source.source_name,
                        "source_version": source.source_version,
                        "source_url": source.source_url,
                        "title": source.title,
                        "chunk_index": index,
                        "content": part,
                        "content_sha256": chunk_sha256,
                        "embedding_model": self.embeddings.model_name,
                    },
                )
            )

        self.client.upsert(collection_name=collection_name, points=points, wait=True)
        current_ids = {str(chunk.point_id) for chunk in indexed_chunks}
        old_ids: list[str | int | UUID] = []
        offset = None
        source_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=source.document_id)
                )
            ]
        )
        while True:
            old_points, offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=source_filter,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            old_ids.extend(point.id for point in old_points if str(point.id) not in current_ids)
            if offset is None:
                break
        if old_ids:
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=old_ids),
                wait=True,
            )
        return indexed_chunks

    def search(
        self,
        *,
        query: str,
        document_type: str,
        tenant_id: str,
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        if document_type not in COLLECTION_BY_TYPE:
            raise ValueError(f"Unsupported document type: {document_type}")
        if not query.strip() or not 1 <= limit <= 50:
            raise ValueError("query must be non-empty and limit must be between 1 and 50")
        collection_name = COLLECTION_BY_TYPE[document_type]
        self.ensure_collections()
        query_filter = models.Filter(
            should=[
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                models.FieldCondition(key="is_public", match=models.MatchValue(value=True)),
            ]
        )
        response = self.client.query_points(
            collection_name=collection_name,
            query=self.embeddings.embed_query(query),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return response.points


def persist_document_index(
    connection: psycopg.Connection,
    source: DocumentSource,
    chunks: Sequence[IndexedChunk],
) -> None:
    connection.execute(
        """INSERT INTO source_documents
           (document_id, tenant_id, document_type, supplier_id, title, source_name,
            source_path, source_version, effective_from, effective_to, is_synthetic,
            content_sha256, ingestion_status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'indexed')
           ON CONFLICT (document_id) DO UPDATE SET
             tenant_id = EXCLUDED.tenant_id, document_type = EXCLUDED.document_type,
             supplier_id = EXCLUDED.supplier_id, title = EXCLUDED.title,
             source_name = EXCLUDED.source_name, source_path = EXCLUDED.source_path,
             source_version = EXCLUDED.source_version, effective_from = EXCLUDED.effective_from,
             effective_to = EXCLUDED.effective_to, is_synthetic = EXCLUDED.is_synthetic,
             content_sha256 = EXCLUDED.content_sha256, ingestion_status = 'indexed'""",
        (
            source.document_id,
            source.tenant_id,
            source.document_type,
            source.supplier_id,
            source.title,
            source.source_name,
            str(source.path),
            source.source_version,
            source.effective_from,
            source.effective_to,
            source.is_synthetic,
            source.content_sha256,
        ),
    )
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (source.document_id,))
        cursor.executemany(
            """INSERT INTO document_chunks
               (chunk_id, document_id, chunk_index, collection_name, point_id, content, content_sha256)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    chunk.point_id,
                    source.document_id,
                    chunk.chunk_index,
                    chunk.collection_name,
                    chunk.point_id,
                    chunk.content,
                    chunk.content_sha256,
                )
                for chunk in chunks
            ],
        )
