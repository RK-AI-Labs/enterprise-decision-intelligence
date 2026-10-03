from datetime import date
from pathlib import Path

from qdrant_client import QdrantClient

from ai_template_python.data_foundation.document_generation import generate_synthetic_documents
from ai_template_python.data_foundation.ingestion import (
    DocumentSource,
    QdrantDocumentIndexer,
    chunk_text,
    load_document_manifest,
)
from ai_template_python.data_foundation.synthetic import (
    SYNTHETIC_TENANT_ID,
    generate_synthetic_dataset,
)


class DeterministicEmbeddings:
    dimensions = 3
    model_name = "test-embeddings"

    def embed_document(self, *, title: str, text: str) -> list[float]:
        return self._vector(f"{title} {text}")

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        return [
            1.0 if "contract" in normalized else 0.0,
            1.0 if "supplier" in normalized else 0.0,
            1.0 if "market" in normalized else 0.0,
        ]


def test_chunking_overlaps_and_manifest_hashes_are_verified(tmp_path: Path) -> None:
    chunks = chunk_text("one two three four five", words_per_chunk=3, overlap_words=1)
    assert chunks == ["one two three", "three four five"]

    document_dir = tmp_path / "documents"
    generate_synthetic_documents(generate_synthetic_dataset(), document_dir)
    sources = load_document_manifest(document_dir / "manifest.json")

    assert len(sources) == 18
    assert all(source.tenant_id == SYNTHETIC_TENANT_ID for source in sources)
    assert all(source.is_synthetic for source in sources)


def test_qdrant_index_is_repeatable_and_scoped_to_tenant(tmp_path: Path) -> None:
    client = QdrantClient(":memory:")
    indexer = QdrantDocumentIndexer(client, DeterministicEmbeddings())
    source = DocumentSource(
        document_id="SYN-CON-S102",
        document_type="contract",
        title="Supplier contract",
        path=tmp_path / "contract.md",
        source_name="synthetic",
        source_version="1",
        content_sha256="abc",
        supplier_id="S102",
        tenant_id=SYNTHETIC_TENANT_ID,
        effective_from=date(2024, 1, 1),
        is_synthetic=True,
    )
    source.path.write_text("Supplier contract price adjustment rules.", encoding="utf-8")

    first = indexer.index_document(source, "Supplier contract price adjustment rules.")
    second = indexer.index_document(source, "Supplier contract updated price rules.")

    assert len(first) == len(second) == 1
    assert first[0].point_id != second[0].point_id
    assert client.get_collection("procurement_contracts").points_count == 1
    assert (
        len(
            indexer.search(
                query="supplier contract",
                document_type="contract",
                tenant_id=SYNTHETIC_TENANT_ID,
            )
        )
        == 1
    )
    assert (
        indexer.search(
            query="supplier contract",
            document_type="contract",
            tenant_id="00000000-0000-4000-8000-000000000002",
        )
        == []
    )
