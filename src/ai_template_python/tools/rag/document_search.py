"""Tenant-scoped semantic document search over the Qdrant knowledge base."""

from os import environ
from typing import Any

from google.adk.tools import ToolContext
from qdrant_client import QdrantClient, models

from ai_template_python.data_foundation.ingestion import (
    COLLECTION_BY_TYPE,
    GeminiEmbeddingProvider,
)
from ai_template_python.evidence import register_evidence

_SEARCHABLE_TYPES = ("contract", "policy", "supplier_profile")


def search_documents(
    query: str,
    document_type: str,
    tool_context: ToolContext,
    supplier_id: str = "",
) -> dict[str, Any]:
    """Semantic search over contracts, procurement policies, or supplier profiles.

    Args:
        query: What to look for, for example "price adjustment cap and approval".
        document_type: One of contract, policy, supplier_profile.
        supplier_id: Optional supplier ID to restrict results, for example S102.
    """
    tenant_id = tool_context.state.get("tenant_id")
    if not tenant_id:
        return {"status": "error", "message": "Authorized tenant context is missing."}
    if document_type not in _SEARCHABLE_TYPES or not query.strip() or len(query) > 500:
        return {"status": "error", "message": "Invalid query or document_type."}
    api_key = environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "GOOGLE_API_KEY is not configured."}

    conditions: list[models.Condition] = [
        models.Filter(
            should=[
                models.FieldCondition(
                    key="tenant_id", match=models.MatchValue(value=str(tenant_id))
                ),
                models.FieldCondition(key="is_public", match=models.MatchValue(value=True)),
            ]
        )
    ]
    if supplier_id.strip():
        conditions.append(
            models.FieldCondition(
                key="supplier_id", match=models.MatchValue(value=supplier_id.strip())
            )
        )

    try:
        client = QdrantClient(
            url=environ.get("QDRANT_URL", "http://localhost:6333"),
            check_compatibility=False,
        )
        vector = GeminiEmbeddingProvider(api_key).embed_query(query.strip())
        points = client.query_points(
            collection_name=COLLECTION_BY_TYPE[document_type],
            query=vector,
            query_filter=models.Filter(must=conditions),
            limit=3,
            with_payload=True,
        ).points
    except Exception:  # noqa: BLE001 - tool errors are returned to the agent, not raised
        return {"status": "error", "message": "The document search could not be completed."}

    results = []
    for point in points:
        payload = point.payload or {}
        document_id = str(payload.get("document_id"))
        content = str(payload.get("content", ""))
        evidence_id = register_evidence(
            tool_context.state,
            source_type="document",
            source_id=document_id,
            locator=f"{document_id}#chunk-{payload.get('chunk_index')}",
            citation_label=str(payload.get("title")),
            excerpt=content,
            is_synthetic=bool(payload.get("is_synthetic")),
        )
        results.append(
            {
                "evidence_id": evidence_id,
                "document_id": document_id,
                "title": payload.get("title"),
                "relevance": round(point.score, 3),
                "content": content[:1500],
            }
        )
    return {"status": "success", "results": results}
