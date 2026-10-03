from decimal import Decimal

from ai_template_python.data_foundation.synthetic import generate_synthetic_dataset


def test_synthetic_dataset_is_repeatable_and_relationally_consistent() -> None:
    first = generate_synthetic_dataset()
    second = generate_synthetic_dataset()

    assert first == second
    assert len(first.suppliers) == 8
    assert len(first.purchase_orders) == 8 * 24
    assert len(first.items) == len(first.purchase_orders)
    assert len(first.invoices) == len(first.purchase_orders)
    assert {order.contract_id for order in first.purchase_orders} == {
        contract.contract_id for contract in first.contracts
    }


def test_synthetic_s102_case_has_price_shock_and_delivery_decline() -> None:
    data = generate_synthetic_dataset()
    s102_orders = [order for order in data.purchase_orders if order.supplier_id == "S102"]
    price_by_month = {
        order.ordered_on: next(
            item.unit_price
            for item in data.items
            if item.purchase_order_id == order.purchase_order_id
        )
        for order in s102_orders
    }
    s102_performance = [row for row in data.performance if row.supplier_id == "S102"]

    assert price_by_month[
        next(day for day in price_by_month if (day.year, day.month) == (2025, 7))
    ] > price_by_month[
        next(day for day in price_by_month if (day.year, day.month) == (2025, 6))
    ] * Decimal("1.14")
    assert s102_performance[-1].on_time_rate < s102_performance[0].on_time_rate
    assert all(supplier.name.startswith("Fictional ") for supplier in data.suppliers)
