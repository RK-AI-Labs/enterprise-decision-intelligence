"""Command-line entry points for the local procurement data foundation."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from qdrant_client import QdrantClient

from ai_template_python.data_foundation.document_generation import generate_synthetic_documents
from ai_template_python.data_foundation.ingestion import (
    GeminiEmbeddingProvider,
    QdrantDocumentIndexer,
    extract_document_text,
    load_document_manifest,
    persist_document_index,
    world_bank_pdf_sources,
)
from ai_template_python.data_foundation.seeding import seed_database
from ai_template_python.data_foundation.synthetic import generate_synthetic_dataset

ROOT = Path.cwd()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} must be set in the environment")
    return value


def _generate_documents(output_dir: Path) -> None:
    count = generate_synthetic_documents(generate_synthetic_dataset(), output_dir)
    print(f"Generated {count} fictional documents in {output_dir}")


def _seed(args: argparse.Namespace) -> None:
    contracts_xml = args.contracts_xml if args.contracts_xml.is_file() else None
    pink_sheet = args.pink_sheet if args.pink_sheet.is_file() else None
    counts = seed_database(
        _required_env("DATABASE_URL"),
        contracts_xml=contracts_xml,
        pink_sheet=pink_sheet,
    )
    print(json.dumps(counts, indent=2, sort_keys=True))


def _ingest_documents(args: argparse.Namespace) -> None:
    sources = load_document_manifest(args.manifest)
    sources.extend(world_bank_pdf_sources(args.data_dir))
    if not sources:
        raise SystemExit("No source documents found; generate the synthetic documents first")

    embeddings = GeminiEmbeddingProvider(_required_env("GOOGLE_API_KEY"))
    qdrant = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    indexer = QdrantDocumentIndexer(qdrant, embeddings)
    indexed_documents = 0
    indexed_chunks = 0
    with psycopg.connect(_required_env("DATABASE_URL")) as connection:
        for source in sources:
            text = extract_document_text(source.path)
            chunks = indexer.index_document(source, text)
            with connection.transaction():
                persist_document_index(connection, source, chunks)
            indexed_documents += 1
            indexed_chunks += len(chunks)
    print(json.dumps({"documents": indexed_documents, "chunks": indexed_chunks}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and index the local procurement data foundation"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser(
        "generate-documents", help="write fictional contracts, policies, and profiles"
    )
    generate.add_argument("--output-dir", type=Path, default=ROOT / "data/synthetic/documents")

    seed = commands.add_parser(
        "seed", help="apply schema and seed synthetic and supplied reference data"
    )
    seed.add_argument("--contracts-xml", type=Path, default=ROOT / "data/uk-contracts.xml")
    seed.add_argument(
        "--pink-sheet",
        type=Path,
        default=ROOT / "data/CMO-Historical-Data-Monthly.xlsx",
    )

    ingest = commands.add_parser(
        "ingest-documents", help="embed documents and index Qdrant collections"
    )
    ingest.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data/synthetic/documents/manifest.json",
    )
    ingest.add_argument("--data-dir", type=Path, default=ROOT / "data")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "generate-documents":
        _generate_documents(args.output_dir)
    elif args.command == "seed":
        _seed(args)
    elif args.command == "ingest-documents":
        _ingest_documents(args)


if __name__ == "__main__":
    main()
