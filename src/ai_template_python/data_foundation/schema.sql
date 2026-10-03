CREATE TABLE IF NOT EXISTS tenants (
    tenant_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS suppliers (
    tenant_id UUID NOT NULL REFERENCES tenants (tenant_id),
    supplier_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    region TEXT NOT NULL,
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high')),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    source_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS contracts (
    tenant_id UUID NOT NULL,
    contract_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    title TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    annual_value_gbp NUMERIC(16, 2) NOT NULL CHECK (annual_value_gbp >= 0),
    price_adjustment_cap_percent NUMERIC(6, 2) NOT NULL CHECK (price_adjustment_cap_percent >= 0),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    source_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, contract_id),
    FOREIGN KEY (tenant_id, supplier_id) REFERENCES suppliers (tenant_id, supplier_id),
    CHECK (start_date <= end_date)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    tenant_id UUID NOT NULL,
    purchase_order_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    ordered_on DATE NOT NULL,
    currency CHAR(3) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'issued', 'invoiced', 'cancelled')),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    source_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, purchase_order_id),
    FOREIGN KEY (tenant_id, supplier_id) REFERENCES suppliers (tenant_id, supplier_id),
    FOREIGN KEY (tenant_id, contract_id) REFERENCES contracts (tenant_id, contract_id)
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    tenant_id UUID NOT NULL,
    item_id TEXT NOT NULL,
    purchase_order_id TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity NUMERIC(14, 3) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(16, 4) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(18, 4) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    PRIMARY KEY (tenant_id, item_id),
    FOREIGN KEY (tenant_id, purchase_order_id)
        REFERENCES purchase_orders (tenant_id, purchase_order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoices (
    tenant_id UUID NOT NULL,
    invoice_id TEXT NOT NULL,
    purchase_order_id TEXT NOT NULL,
    invoiced_on DATE NOT NULL,
    amount NUMERIC(18, 4) NOT NULL CHECK (amount >= 0),
    currency CHAR(3) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('received', 'approved', 'paid', 'disputed')),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    source_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, invoice_id),
    UNIQUE (tenant_id, purchase_order_id),
    FOREIGN KEY (tenant_id, purchase_order_id)
        REFERENCES purchase_orders (tenant_id, purchase_order_id)
);

CREATE TABLE IF NOT EXISTS supplier_performance (
    tenant_id UUID NOT NULL,
    supplier_id TEXT NOT NULL,
    month DATE NOT NULL,
    on_time_rate NUMERIC(5, 4) NOT NULL CHECK (on_time_rate BETWEEN 0 AND 1),
    defect_rate NUMERIC(5, 4) NOT NULL CHECK (defect_rate BETWEEN 0 AND 1),
    quality_score NUMERIC(5, 4) NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    source_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, supplier_id, month),
    FOREIGN KEY (tenant_id, supplier_id) REFERENCES suppliers (tenant_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS commodity_observations (
    source_name TEXT NOT NULL,
    series_id TEXT NOT NULL,
    country_code TEXT NOT NULL,
    observed_on DATE NOT NULL,
    value NUMERIC(20, 6) NOT NULL,
    unit TEXT NOT NULL,
    currency CHAR(3),
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    source_version TEXT,
    PRIMARY KEY (source_name, series_id, country_code, observed_on)
);

CREATE TABLE IF NOT EXISTS contracts_finder_notices (
    source_notice_id TEXT PRIMARY KEY,
    notice_identifier TEXT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT,
    organisation_name TEXT,
    cpv_description TEXT,
    notice_type TEXT,
    published_at TIMESTAMPTZ,
    deadline_at TIMESTAMPTZ,
    contract_start DATE,
    contract_end DATE,
    value_low_gbp NUMERIC(18, 2),
    value_high_gbp NUMERIC(18, 2),
    region TEXT,
    postcode TEXT,
    source_file TEXT NOT NULL,
    source_file_sha256 CHAR(64) NOT NULL,
    raw_notice JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contracts_finder_awards (
    source_notice_id TEXT NOT NULL REFERENCES contracts_finder_notices (source_notice_id) ON DELETE CASCADE,
    source_award_id TEXT NOT NULL,
    supplier_name TEXT,
    supplier_reference TEXT,
    awarded_value_gbp NUMERIC(18, 2),
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    awarded_at TIMESTAMPTZ,
    PRIMARY KEY (source_notice_id, source_award_id)
);

CREATE TABLE IF NOT EXISTS source_documents (
    document_id TEXT PRIMARY KEY,
    tenant_id UUID REFERENCES tenants (tenant_id),
    document_type TEXT NOT NULL CHECK (
        document_type IN ('contract', 'policy', 'supplier_profile', 'market_report')
    ),
    supplier_id TEXT,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_version TEXT NOT NULL,
    effective_from DATE,
    effective_to DATE,
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    content_sha256 CHAR(64) NOT NULL,
    ingestion_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        ingestion_status IN ('pending', 'indexed', 'failed', 'superseded')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id UUID PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_documents (document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    collection_name TEXT NOT NULL,
    point_id UUID NOT NULL UNIQUE,
    content TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id UUID PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_written INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_tenant_ordered_on
    ON purchase_orders (tenant_id, ordered_on);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier_date
    ON purchase_orders (tenant_id, supplier_id, ordered_on);
CREATE INDEX IF NOT EXISTS idx_purchase_order_items_category
    ON purchase_order_items (tenant_id, category);
CREATE INDEX IF NOT EXISTS idx_supplier_performance_month
    ON supplier_performance (tenant_id, month);
CREATE INDEX IF NOT EXISTS idx_commodity_observations_series_date
    ON commodity_observations (source_name, series_id, observed_on);
CREATE INDEX IF NOT EXISTS idx_contracts_finder_status_published
    ON contracts_finder_notices (status, published_at);
CREATE INDEX IF NOT EXISTS idx_contracts_finder_organisation
    ON contracts_finder_notices (organisation_name);
CREATE INDEX IF NOT EXISTS idx_source_documents_type_supplier
    ON source_documents (document_type, supplier_id);