"""Deterministic, explicitly synthetic procurement data for local development."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from random import Random

SYNTHETIC_TENANT_ID = "00000000-0000-4000-8000-000000000001"


@dataclass(frozen=True, slots=True)
class SyntheticSupplier:
    supplier_id: str
    name: str
    category: str
    region: str
    risk_tier: str


@dataclass(frozen=True, slots=True)
class SyntheticContract:
    contract_id: str
    supplier_id: str
    title: str
    start_date: date
    end_date: date
    annual_value_gbp: Decimal
    price_adjustment_cap_percent: Decimal


@dataclass(frozen=True, slots=True)
class SyntheticPurchaseOrder:
    purchase_order_id: str
    supplier_id: str
    contract_id: str
    ordered_on: date
    currency: str
    status: str


@dataclass(frozen=True, slots=True)
class SyntheticPurchaseOrderItem:
    item_id: str
    purchase_order_id: str
    description: str
    category: str
    quantity: Decimal
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


@dataclass(frozen=True, slots=True)
class SyntheticInvoice:
    invoice_id: str
    purchase_order_id: str
    invoiced_on: date
    amount: Decimal
    currency: str
    status: str


@dataclass(frozen=True, slots=True)
class SyntheticSupplierPerformance:
    supplier_id: str
    month: date
    on_time_rate: Decimal
    defect_rate: Decimal
    quality_score: Decimal


@dataclass(frozen=True, slots=True)
class SyntheticDataset:
    suppliers: tuple[SyntheticSupplier, ...]
    contracts: tuple[SyntheticContract, ...]
    purchase_orders: tuple[SyntheticPurchaseOrder, ...]
    items: tuple[SyntheticPurchaseOrderItem, ...]
    invoices: tuple[SyntheticInvoice, ...]
    performance: tuple[SyntheticSupplierPerformance, ...]


_SUPPLIERS = (
    ("S101", "Fictional Northstar Components Ltd", "electronic-components", "Midlands"),
    ("S102", "Fictional Meridian Industrial Supply Ltd", "industrial-components", "North West"),
    ("S103", "Fictional Alder Materials Group Ltd", "metals", "Yorkshire"),
    ("S104", "Fictional Brookline Packaging Ltd", "packaging", "South East"),
    ("S105", "Fictional Cairn Logistics Services Ltd", "logistics", "Scotland"),
    ("S106", "Fictional Delta Precision Manufacturing Ltd", "industrial-components", "Wales"),
    ("S107", "Fictional Estuary Electrical Systems Ltd", "electronic-components", "South West"),
    ("S108", "Fictional Fenland Materials Ltd", "metals", "East of England"),
)


def generate_synthetic_dataset(seed: int = 20261003) -> SyntheticDataset:
    """Generate a stable 24-month dataset with a known S102 investigation case."""
    random = Random(seed)
    suppliers: list[SyntheticSupplier] = []
    contracts: list[SyntheticContract] = []
    purchase_orders: list[SyntheticPurchaseOrder] = []
    items: list[SyntheticPurchaseOrderItem] = []
    invoices: list[SyntheticInvoice] = []
    performance: list[SyntheticSupplierPerformance] = []

    for supplier_index, (supplier_id, name, category, region) in enumerate(_SUPPLIERS):
        risk_tier = "high" if supplier_id == "S102" else "low"
        suppliers.append(SyntheticSupplier(supplier_id, name, category, region, risk_tier))
        contract_id = f"SYN-CON-{supplier_id}"
        contracts.append(
            SyntheticContract(
                contract_id=contract_id,
                supplier_id=supplier_id,
                title=f"{name} supply agreement",
                start_date=date(2024, 1, 1),
                end_date=date(2026, 6, 30),
                annual_value_gbp=Decimal(120_000 + supplier_index * 18_500),
                price_adjustment_cap_percent=Decimal("5.00"),
            )
        )

        base_price = Decimal(18 + supplier_index * 7)
        for month_index in range(24):
            year = 2024 + month_index // 12
            month = month_index % 12 + 1
            ordered_on = date(year, month, 5 + supplier_index % 12)
            purchase_order_id = f"SYN-PO-{supplier_id}-{year}{month:02d}"
            quantity = Decimal(40 + random.randrange(0, 61))
            inflation = Decimal("1") + Decimal(month_index) * Decimal("0.002")
            adjustment = (
                Decimal("1.15")
                if supplier_id == "S102" and (year, month) >= (2025, 7)
                else Decimal("1")
            )
            unit_price = (base_price * inflation * adjustment).quantize(Decimal("0.01"))
            purchase_orders.append(
                SyntheticPurchaseOrder(
                    purchase_order_id=purchase_order_id,
                    supplier_id=supplier_id,
                    contract_id=contract_id,
                    ordered_on=ordered_on,
                    currency="GBP",
                    status="invoiced",
                )
            )
            item = SyntheticPurchaseOrderItem(
                item_id=f"{purchase_order_id}-01",
                purchase_order_id=purchase_order_id,
                description=f"{category.replace('-', ' ').title()} supply lot",
                category=category,
                quantity=quantity,
                unit_price=unit_price,
            )
            items.append(item)
            invoices.append(
                SyntheticInvoice(
                    invoice_id=f"SYN-INV-{supplier_id}-{year}{month:02d}",
                    purchase_order_id=purchase_order_id,
                    invoiced_on=date(year, month, min(20, 12 + supplier_index % 10)),
                    amount=item.line_total,
                    currency="GBP",
                    status="paid",
                )
            )

            if supplier_id == "S102":
                on_time = Decimal("0.94") - Decimal(max(0, month_index - 17)) * Decimal("0.025")
                defect = Decimal("0.012") + Decimal(max(0, month_index - 17)) * Decimal("0.003")
            else:
                on_time = Decimal("0.94") + Decimal((supplier_index % 3) - 1) * Decimal("0.01")
                defect = Decimal("0.012") + Decimal(supplier_index % 3) * Decimal("0.002")
            performance.append(
                SyntheticSupplierPerformance(
                    supplier_id=supplier_id,
                    month=date(year, month, 1),
                    on_time_rate=max(Decimal("0"), on_time).quantize(Decimal("0.001")),
                    defect_rate=defect.quantize(Decimal("0.001")),
                    quality_score=(Decimal("1") - defect).quantize(Decimal("0.001")),
                )
            )

    return SyntheticDataset(
        suppliers=tuple(suppliers),
        contracts=tuple(contracts),
        purchase_orders=tuple(purchase_orders),
        items=tuple(items),
        invoices=tuple(invoices),
        performance=tuple(performance),
    )
