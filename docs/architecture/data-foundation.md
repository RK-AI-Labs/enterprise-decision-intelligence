# Data Foundation

## Data Boundaries

This milestone combines three deliberately separate sources:

| Source | Use | Provenance and handling |
| --- | --- | --- |
| `data/uk-contracts.xml` | 1,000 public Contracts Finder notices and award records | Imported as external notices, not as internal purchase orders. Notice and award IDs, statuses, nullable values, source filename, file hash, and raw notice fields are retained. |
| `data/CMO-Historical-Data-Monthly.xlsx` | World Bank Pink Sheet monthly commodity observations | Imports numeric cells from `Monthly Prices`; 50,451 observations across 71 series in the supplied workbook. Units, series, month, USD currency where specified, retrieval time, and workbook hash are recorded. |
| `data/synthetic/documents/` and the synthetic PostgreSQL tenant | Procurement transactions and reference documents for deterministic scenarios | Every generated supplier, contract, PO, invoice, metric, profile, and policy is labeled synthetic. Names are fictional. |

The annual Pink Sheet workbook is retained as supplied but is not loaded by default because it duplicates the monthly series at a different frequency. The World Bank PDFs are indexed as market-report documents, with file hashes and the public source landing page. Public API observations are kept separate from generated transactions. No LLM-generated narrative is treated as source data.

## PostgreSQL

The schema is in `src/ai_template_python/data_foundation/schema.sql`. It covers tenants, suppliers, contracts, purchase orders and lines, invoices, supplier performance, commodity observations, imported Contracts Finder notices/awards, source documents/chunks, and ingestion runs. Composite tenant keys protect internal records; public notices retain their own source identity. Monetary values use `NUMERIC`, dates retain source precision/time zones where relevant, and foreign keys connect the synthetic procurement records.

Seeding is idempotent. Re-running a seed updates the same stable synthetic IDs and source notice/series keys instead of appending duplicate rows. All locally generated values are tagged `is_synthetic` and `source_name='synthetic_generator'`.

## Synthetic Scenario

The deterministic generator produces eight fictional suppliers, eight agreements, and 24 monthly periods of linked orders, line items, invoices, and supplier-performance measures. Supplier `S102` has a modeled 15% unit-price step beginning July 2025 and declining on-time delivery; its fictional agreement caps annual price changes at 5% and requires approval. This is a test scenario, not a claim about a real supplier or market.

The document generator writes one profile and one agreement per supplier plus two policies. Every document begins with a synthetic-data notice and the JSON manifest records type, supplier, effective dates, source version, and SHA-256 content hash. The document ingestion step rejects manifest path escapes and content/hash mismatches.

## Qdrant Collections

The vector size is 768 using `gemini-embedding-2`; collection dimensions and model must match. Four cosine collections are defined:

- `procurement_contracts`
- `procurement_policies`
- `supplier_profiles`
- `market_reports`

Payloads contain document IDs, source version, tenant/public visibility, synthetic flag, supplier, title, text chunk, and content hash. PostgreSQL stores the citation text and chunk-to-source mapping. Stable point IDs make re-indexing idempotent; obsolete chunks for a changed document are removed. Retrieval requires a tenant ID and includes explicitly public records only.

Gemini embeddings require `GOOGLE_API_KEY`. The local Qdrant service itself has no authentication by default; keep it bound to a trusted local network and configure authentication/TLS before exposing it outside development.

## External Adapters

`data_foundation/external_sources.py` contains typed clients:

- World Bank Indicators API v2: public; requests paginated indicator observations.
- FRED: requires `FRED_API_KEY`; reads series observations and skips the API's `.` missing-value marker.
- USAspending: public award-search endpoint; sends bounded date-filtered contract queries.
- SEC EDGAR: reads company facts/submissions; requires an identifying `SEC_USER_AGENT` and CIK validation.
- Contracts Finder OCDS: reads paginated published release packages. The supplied XML export is imported separately through the streaming XML parser.

All clients take injectable `httpx` clients for offline tests and use bounded connect/read timeouts. They do not log API keys. FRED observations go into the normalized `commodity_observations` shape; public notices and internal purchase orders remain distinct. API calls are opt-in and are not required for local database seeding.

## Local Workflow

1. Install notebook tools: `uv sync --group notebook`.
2. Explore raw sources before loading: `uv run --group notebook jupyter lab notebooks/data_foundation_eda.ipynb`. This offline EDA path does not require a `.env` file.
3. Live API examples in the notebook are disabled by default. To enable them, create `.env` from `.env.example`, set the credentials for the providers you want to try, and launch Jupyter with `uv run --env-file .env --group notebook jupyter lab notebooks/data_foundation_eda.ipynb`.
4. Start local data services: `docker compose up -d postgres qdrant`.
5. Generate synthetic documents: `uv run python -m ai_template_python.data_foundation generate-documents`.
6. Before seeding or embedding documents, create `.env` from `.env.example` and configure `DATABASE_URL`; document indexing also needs `GOOGLE_API_KEY`.
7. Apply the schema and load synthetic records plus supplied XML/Pink Sheet data: `uv run --env-file .env python -m ai_template_python.data_foundation seed`.
8. Extract, embed, persist, and index generated Markdown plus the supplied World Bank PDFs: `uv run --env-file .env python -m ai_template_python.data_foundation ingest-documents`.

Seed operations require only local files and PostgreSQL. Document indexing additionally requires Qdrant and a working Gemini API key. Live source adapters are callable independently and are not contacted during seed runs or tests.