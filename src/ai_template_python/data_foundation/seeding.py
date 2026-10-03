"""Idempotent PostgreSQL setup and seed operations."""

import hashlib
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from ai_template_python.data_foundation.commodity_data import iter_pink_sheet_monthly
from ai_template_python.data_foundation.contracts_finder import (
    iter_contracts_finder_notices,
)
from ai_template_python.data_foundation.external_sources import ExternalObservation
from ai_template_python.data_foundation.synthetic import (
    SYNTHETIC_TENANT_ID,
    SyntheticDataset,
    generate_synthetic_dataset,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
TENANT_NAME = "Synthetic Procurement Sandbox"


def _executemany(
    connection: psycopg.Connection,
    query: str,
    rows: Sequence[Sequence[object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(query, rows)


def apply_schema(connection: psycopg.Connection) -> None:
    connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed_synthetic_procurement(
    connection: psycopg.Connection,
    dataset: SyntheticDataset | None = None,
) -> dict[str, int]:
    """Upsert a deterministic tenant and linked synthetic procurement history."""
    dataset = dataset or generate_synthetic_dataset()
    tenant_id = UUID(SYNTHETIC_TENANT_ID)
    connection.execute(
        """INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)
           ON CONFLICT (tenant_id) DO UPDATE SET name = EXCLUDED.name""",
        (tenant_id, TENANT_NAME),
    )
    _executemany(
        connection,
        """INSERT INTO suppliers
           (tenant_id, supplier_id, name, category, region, risk_tier, is_synthetic, source_name)
           VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'synthetic_generator')
           ON CONFLICT (tenant_id, supplier_id) DO UPDATE SET
             name = EXCLUDED.name, category = EXCLUDED.category, region = EXCLUDED.region,
             risk_tier = EXCLUDED.risk_tier, is_synthetic = TRUE,
             source_name = EXCLUDED.source_name""",
        [
            (
                tenant_id,
                supplier.supplier_id,
                supplier.name,
                supplier.category,
                supplier.region,
                supplier.risk_tier,
            )
            for supplier in dataset.suppliers
        ],
    )
    _executemany(
        connection,
        """INSERT INTO contracts
           (tenant_id, contract_id, supplier_id, title, start_date, end_date,
            annual_value_gbp, price_adjustment_cap_percent, is_synthetic, source_name)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'synthetic_generator')
           ON CONFLICT (tenant_id, contract_id) DO UPDATE SET
             supplier_id = EXCLUDED.supplier_id, title = EXCLUDED.title,
             start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
             annual_value_gbp = EXCLUDED.annual_value_gbp,
             price_adjustment_cap_percent = EXCLUDED.price_adjustment_cap_percent,
             is_synthetic = TRUE, source_name = EXCLUDED.source_name""",
        [
            (
                tenant_id,
                contract.contract_id,
                contract.supplier_id,
                contract.title,
                contract.start_date,
                contract.end_date,
                contract.annual_value_gbp,
                contract.price_adjustment_cap_percent,
            )
            for contract in dataset.contracts
        ],
    )
    _executemany(
        connection,
        """INSERT INTO purchase_orders
           (tenant_id, purchase_order_id, supplier_id, contract_id, ordered_on,
            currency, status, is_synthetic, source_name)
           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, 'synthetic_generator')
           ON CONFLICT (tenant_id, purchase_order_id) DO UPDATE SET
             supplier_id = EXCLUDED.supplier_id, contract_id = EXCLUDED.contract_id,
             ordered_on = EXCLUDED.ordered_on, currency = EXCLUDED.currency,
             status = EXCLUDED.status, is_synthetic = TRUE, source_name = EXCLUDED.source_name""",
        [
            (
                tenant_id,
                order.purchase_order_id,
                order.supplier_id,
                order.contract_id,
                order.ordered_on,
                order.currency,
                order.status,
            )
            for order in dataset.purchase_orders
        ],
    )
    _executemany(
        connection,
        """INSERT INTO purchase_order_items
           (tenant_id, item_id, purchase_order_id, description, category, quantity, unit_price)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (tenant_id, item_id) DO UPDATE SET
             purchase_order_id = EXCLUDED.purchase_order_id, description = EXCLUDED.description,
             category = EXCLUDED.category, quantity = EXCLUDED.quantity,
             unit_price = EXCLUDED.unit_price""",
        [
            (
                tenant_id,
                item.item_id,
                item.purchase_order_id,
                item.description,
                item.category,
                item.quantity,
                item.unit_price,
            )
            for item in dataset.items
        ],
    )
    _executemany(
        connection,
        """INSERT INTO invoices
           (tenant_id, invoice_id, purchase_order_id, invoiced_on, amount, currency,
            status, is_synthetic, source_name)
           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, 'synthetic_generator')
           ON CONFLICT (tenant_id, invoice_id) DO UPDATE SET
             purchase_order_id = EXCLUDED.purchase_order_id, invoiced_on = EXCLUDED.invoiced_on,
             amount = EXCLUDED.amount, currency = EXCLUDED.currency, status = EXCLUDED.status,
             is_synthetic = TRUE, source_name = EXCLUDED.source_name""",
        [
            (
                tenant_id,
                invoice.invoice_id,
                invoice.purchase_order_id,
                invoice.invoiced_on,
                invoice.amount,
                invoice.currency,
                invoice.status,
            )
            for invoice in dataset.invoices
        ],
    )
    _executemany(
        connection,
        """INSERT INTO supplier_performance
           (tenant_id, supplier_id, month, on_time_rate, defect_rate, quality_score,
            is_synthetic, source_name)
           VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'synthetic_generator')
           ON CONFLICT (tenant_id, supplier_id, month) DO UPDATE SET
             on_time_rate = EXCLUDED.on_time_rate, defect_rate = EXCLUDED.defect_rate,
             quality_score = EXCLUDED.quality_score, is_synthetic = TRUE,
             source_name = EXCLUDED.source_name""",
        [
            (
                tenant_id,
                row.supplier_id,
                row.month,
                row.on_time_rate,
                row.defect_rate,
                row.quality_score,
            )
            for row in dataset.performance
        ],
    )
    return {
        "suppliers": len(dataset.suppliers),
        "contracts": len(dataset.contracts),
        "purchase_orders": len(dataset.purchase_orders),
        "purchase_order_items": len(dataset.items),
        "invoices": len(dataset.invoices),
        "supplier_performance": len(dataset.performance),
    }


def seed_contracts_finder_xml(
    connection: psycopg.Connection,
    xml_path: str | Path,
) -> int:
    """Import public notices and awards from a downloaded Contracts Finder XML export."""
    path = Path(xml_path)
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    records_written = 0
    for notice in iter_contracts_finder_notices(path):
        connection.execute(
            """INSERT INTO contracts_finder_notices
               (source_notice_id, notice_identifier, title, description, status,
                organisation_name, cpv_description, notice_type, published_at, deadline_at,
                contract_start, contract_end, value_low_gbp, value_high_gbp, region, postcode,
                source_file, source_file_sha256, raw_notice)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (source_notice_id) DO UPDATE SET
                 notice_identifier = EXCLUDED.notice_identifier, title = EXCLUDED.title,
                 description = EXCLUDED.description, status = EXCLUDED.status,
                 organisation_name = EXCLUDED.organisation_name,
                 cpv_description = EXCLUDED.cpv_description, notice_type = EXCLUDED.notice_type,
                 published_at = EXCLUDED.published_at, deadline_at = EXCLUDED.deadline_at,
                 contract_start = EXCLUDED.contract_start, contract_end = EXCLUDED.contract_end,
                 value_low_gbp = EXCLUDED.value_low_gbp, value_high_gbp = EXCLUDED.value_high_gbp,
                 region = EXCLUDED.region, postcode = EXCLUDED.postcode,
                 source_file = EXCLUDED.source_file, source_file_sha256 = EXCLUDED.source_file_sha256,
                 raw_notice = EXCLUDED.raw_notice, imported_at = now()""",
            (
                notice.source_notice_id,
                notice.identifier,
                notice.title,
                notice.description,
                notice.status,
                notice.organisation_name,
                notice.cpv_description,
                notice.notice_type,
                notice.published_at,
                notice.deadline_at,
                notice.contract_start.date() if notice.contract_start else None,
                notice.contract_end.date() if notice.contract_end else None,
                notice.value_low_gbp,
                notice.value_high_gbp,
                notice.region,
                notice.postcode,
                path.name,
                source_sha256,
                Jsonb(notice.raw_notice),
            ),
        )
        for award_index, award in enumerate(notice.awards):
            source_award_id = award.award_id or f"award-{award_index}"
            connection.execute(
                """INSERT INTO contracts_finder_awards
                   (source_notice_id, source_award_id, supplier_name, supplier_reference,
                    awarded_value_gbp, start_date, end_date, awarded_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (source_notice_id, source_award_id) DO UPDATE SET
                     supplier_name = EXCLUDED.supplier_name,
                     supplier_reference = EXCLUDED.supplier_reference,
                     awarded_value_gbp = EXCLUDED.awarded_value_gbp,
                     start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
                     awarded_at = EXCLUDED.awarded_at""",
                (
                    notice.source_notice_id,
                    source_award_id,
                    award.supplier_name,
                    award.supplier_reference,
                    award.awarded_value_gbp,
                    award.start_date,
                    award.end_date,
                    award.awarded_date,
                ),
            )
        records_written += 1
    return records_written


def seed_world_bank_pink_sheet(
    connection: psycopg.Connection,
    workbook_path: str | Path,
) -> int:
    """Upsert monthly World Bank commodity observations from the supplied workbook."""
    rows = [
        (
            item.source_name,
            item.series_id,
            item.country_code,
            item.observed_on,
            item.value,
            item.unit,
            item.currency,
            item.source_url,
            item.retrieved_at,
            item.source_version,
        )
        for item in iter_pink_sheet_monthly(workbook_path)
    ]
    if not rows:
        return 0
    _executemany(
        connection,
        """INSERT INTO commodity_observations
           (source_name, series_id, country_code, observed_on, value, unit, currency,
            source_url, retrieved_at, source_version)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (source_name, series_id, country_code, observed_on) DO UPDATE SET
             value = EXCLUDED.value, unit = EXCLUDED.unit, currency = EXCLUDED.currency,
             source_url = EXCLUDED.source_url, retrieved_at = EXCLUDED.retrieved_at,
             source_version = EXCLUDED.source_version""",
        rows,
    )
    return len(rows)


def store_external_observations(
    connection: psycopg.Connection,
    observations: Sequence[ExternalObservation],
) -> int:
    """Persist normalized World Bank/FRED observations with retrieval provenance."""
    rows = [
        (
            item.source_name,
            item.series_id,
            item.country_code,
            item.observed_on,
            item.value,
            item.unit,
            item.currency,
            item.source_url,
            item.retrieved_at,
            item.source_version,
        )
        for item in observations
    ]
    if not rows:
        return 0
    _executemany(
        connection,
        """INSERT INTO commodity_observations
           (source_name, series_id, country_code, observed_on, value, unit, currency,
            source_url, retrieved_at, source_version)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (source_name, series_id, country_code, observed_on) DO UPDATE SET
             value = EXCLUDED.value, unit = EXCLUDED.unit, currency = EXCLUDED.currency,
             source_url = EXCLUDED.source_url, retrieved_at = EXCLUDED.retrieved_at,
             source_version = EXCLUDED.source_version""",
        rows,
    )
    return len(rows)


def seed_database(
    database_url: str,
    contracts_xml: str | Path | None = None,
    pink_sheet: str | Path | None = None,
) -> dict[str, int]:
    """Apply the schema and seed demo data in one atomic transaction."""
    with psycopg.connect(database_url) as connection:
        apply_schema(connection)
        counts = seed_synthetic_procurement(connection)
        if contracts_xml is not None:
            counts["contracts_finder_notices"] = seed_contracts_finder_xml(
                connection,
                contracts_xml,
            )
        if pink_sheet is not None:
            counts["commodity_observations"] = seed_world_bank_pink_sheet(
                connection,
                pink_sheet,
            )
    return counts


def new_ingestion_run_id() -> UUID:
    return uuid4()
