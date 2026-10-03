from datetime import date
from decimal import Decimal

from openpyxl import Workbook

from ai_template_python.data_foundation.commodity_data import iter_pink_sheet_monthly


def test_pink_sheet_monthly_loader_maps_series_units_and_missing_values(tmp_path) -> None:
    path = tmp_path / "pink-sheet.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Monthly Prices"
    sheet.append(["World Bank Commodity Price Data"])
    sheet.append(["monthly prices"])
    sheet.append(["units in US dollars"])
    sheet.append(["Updated on test date"])
    sheet.append([None, "Crude oil, average", "Copper"])
    sheet.append([None, "($/bbl)", "($/mt)"])
    sheet.append(["2025M01", 75.25, "…"])
    sheet.append(["2025M02", None, 9000])
    workbook.save(path)

    observations = list(iter_pink_sheet_monthly(path))

    assert len(observations) == 2
    assert observations[0].series_id == "crude-oil-average"
    assert observations[0].observed_on == date(2025, 1, 1)
    assert observations[0].value == Decimal("75.25")
    assert observations[1].series_id == "copper"
    assert observations[1].currency == "USD"
    assert observations[1].value == Decimal("9000")
