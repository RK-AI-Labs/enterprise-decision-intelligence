"""Generate clearly labeled fictional contract, policy, and supplier documents."""

import hashlib
import json
from datetime import date
from pathlib import Path

from ai_template_python.data_foundation.synthetic import SyntheticDataset


def generate_synthetic_documents(dataset: SyntheticDataset, output_dir: str | Path) -> int:
    """Write deterministic Markdown documents and an ingestion manifest."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    def add_document(
        document_id: str,
        document_type: str,
        title: str,
        filename: str,
        body: str,
        *,
        supplier_id: str | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
    ) -> None:
        content = (
            "> SYNTHETIC PORTFOLIO DATA. This fictional document is generated for local testing.\n\n"
            f"# {title}\n\n{body.strip()}\n"
        )
        path = destination / filename
        path.write_text(content, encoding="utf-8")
        manifest.append(
            {
                "document_id": document_id,
                "document_type": document_type,
                "title": title,
                "supplier_id": supplier_id,
                "path": filename,
                "source_name": "synthetic_document_generator",
                "source_version": "1",
                "effective_from": effective_from.isoformat() if effective_from else None,
                "effective_to": effective_to.isoformat() if effective_to else None,
                "is_synthetic": True,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )

    contracts = {contract.supplier_id: contract for contract in dataset.contracts}
    for supplier in dataset.suppliers:
        contract = contracts[supplier.supplier_id]
        adjustment_clause = (
            "A documented annual adjustment may not exceed 5% and requires buyer approval. "
            "Any request above the cap requires a written cost breakdown and an executed amendment."
            if supplier.supplier_id == "S102"
            else "Any annual price adjustment requires 90 days' written notice and buyer approval."
        )
        add_document(
            f"SYN-DOC-CON-{supplier.supplier_id}",
            "contract",
            contract.title,
            f"contract-{supplier.supplier_id.lower()}.md",
            f"""## Parties and term

Buyer: Example Procurement Group (fictional). Supplier: {supplier.name}.
Contract reference: {contract.contract_id}. Effective 2024-01-01 through 2026-06-30.
Category: {supplier.category}. All stated amounts are GBP.

## Pricing and adjustment

Annual reference value: GBP {contract.annual_value_gbp:,.2f}. {adjustment_clause}
Invoices must reference an approved purchase order. Disputed price changes do not
automatically amend existing purchase orders.

## Delivery and records

The supplier reports monthly delivery and quality metrics. Both parties retain
purchase-order, invoice, and adjustment records for audit.""",
            supplier_id=supplier.supplier_id,
            effective_from=contract.start_date,
            effective_to=contract.end_date,
        )
        metric_context = (
            "Recent fictional delivery records show deterioration during the second half of 2025."
            if supplier.supplier_id == "S102"
            else "No modeled material delivery incident is present in this fictional profile."
        )
        add_document(
            f"SYN-DOC-PROFILE-{supplier.supplier_id}",
            "supplier_profile",
            f"Supplier profile: {supplier.name}",
            f"supplier-{supplier.supplier_id.lower()}.md",
            f"""## Profile

Supplier ID: {supplier.supplier_id}. Category: {supplier.category}. Region: {supplier.region}.
Modeled risk tier: {supplier.risk_tier}. This profile contains synthetic portfolio data only.

## Performance note

{metric_context} Consult the structured supplier-performance table for dated values;
this narrative is not a substitute for those measurements.""",
            supplier_id=supplier.supplier_id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2025, 12, 31),
        )

    policy_documents = (
        (
            "SYN-DOC-POL-PRICE-001",
            "Procurement policy: price adjustments",
            "policy-price-adjustments.md",
            """## Review requirements

Price adjustments require a current contract clause, a supplier cost breakdown,
and comparison with an independent and relevant market series. A market index is
context, not automatic proof that a supplier's requested increase is justified.

Changes above a contractual cap require documented procurement-owner approval and
a signed contract amendment before the revised price is used. Record the original
price, requested price, calculation, evidence sources, approver, and decision date.

## Evidence handling

Separate verified transaction facts from assessments and recommendations. Cite the
source and effective date for every contractual term used in a decision.""",
        ),
        (
            "SYN-DOC-POL-SUPPLIER-002",
            "Procurement policy: supplier performance and renewal",
            "policy-supplier-performance.md",
            """## Supplier review

Review spend trend, on-time delivery, defect rate, open disputes, and contract
expiry together. Investigate sustained deterioration against the approved service
thresholds before renewal. Do not infer causality from correlation alone.

## Escalation

Escalate material evidence conflicts and missing source records to the procurement
owner. Recommendations do not authorize a purchase-order change or supplier contact.""",
        ),
    )
    for document_id, title, filename, body in policy_documents:
        add_document(
            document_id,
            "policy",
            title,
            filename,
            body,
            effective_from=date(2024, 1, 1),
        )

    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return len(manifest)
