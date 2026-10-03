from datetime import date
from decimal import Decimal

import httpx
import pytest

from ai_template_python.data_foundation.external_sources import (
    ContractsFinderOCDSClient,
    FredClient,
    SecEdgarClient,
    USAspendingClient,
    WorldBankIndicatorsClient,
)


def _client(base_url: str, handler) -> httpx.Client:
    return httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler))


def test_world_bank_indicator_paginates_and_skips_missing_values() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        records = (
            [{"countryiso3code": "GBR", "date": "2024", "value": "2.5", "unit": ""}]
            if page == 1
            else [
                {"countryiso3code": "GBR", "date": "2025", "value": None},
                {"countryiso3code": "GBR", "date": "2025", "value": "3.1"},
            ]
        )
        return httpx.Response(200, json=[{"pages": 2, "lastupdated": "2026-09-01"}, records])

    api = WorldBankIndicatorsClient(_client("https://api.worldbank.org/v2", respond))
    results = api.get_indicator(
        country_code="GBR",
        indicator_id="FP.CPI.TOTL.ZG",
        start_year=2024,
        end_year=2025,
    )

    assert len(requests) == 2
    assert [item.value for item in results] == [Decimal("2.5"), Decimal("3.1")]
    assert results[0].country_code == "GBR"


def test_world_bank_empty_result_page_returns_no_observations() -> None:
    client = _client(
        "https://api.worldbank.org/v2",
        lambda request: httpx.Response(200, json=[{"pages": 0}, None]),
    )
    adapter = WorldBankIndicatorsClient(client)

    assert (
        adapter.get_indicator(
            country_code="GBR",
            indicator_id="FP.CPI.TOTL.ZG",
            start_year=2024,
            end_year=2024,
        )
        == []
    )


def test_fred_observations_skip_missing_values_and_paginate() -> None:
    offsets = []

    def respond(request: httpx.Request) -> httpx.Response:
        offsets.append(int(request.url.params["offset"]))
        if offsets[-1] == 0:
            return httpx.Response(
                200,
                json={
                    "count": 2,
                    "units": "Percent",
                    "observations": [{"date": "2025-01-01", "value": "."}],
                },
            )
        return httpx.Response(
            200,
            json={
                "count": 2,
                "units": "Percent",
                "observations": [{"date": "2025-02-01", "value": "2.75"}],
            },
        )

    client = FredClient("test-key", _client("https://api.stlouisfed.org/fred", respond))
    results = client.get_observations(
        series_id="CPIAUCSL",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 28),
    )

    assert offsets == [0, 1]
    assert len(results) == 1
    assert results[0].value == Decimal("2.75")


def test_usaspending_normalizes_contract_awards() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert '"award_type_codes"' in body
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "Award ID": "CONT_AWD_1",
                        "Recipient Name": "Public Supplier",
                        "Award Amount": 1234.5,
                        "Start Date": "2025-01-01",
                        "End Date": "2025-12-31",
                        "Awarding Agency": "Example Agency",
                        "Award Type": "A",
                    }
                ]
            },
        )

    client = USAspendingClient(_client("https://api.usaspending.gov/api/v2", respond))
    awards = client.search_contract_awards(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert awards[0].award_id == "CONT_AWD_1"
    assert awards[0].award_amount == Decimal("1234.5")
    assert awards[0].recipient_name == "Public Supplier"


def test_sec_requires_contact_user_agent_and_pads_cik() -> None:
    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"facts": {}, "entityName": "Example"})

    with pytest.raises(ValueError, match="contact email"):
        SecEdgarClient("Portfolio app")

    client = SecEdgarClient(
        "Portfolio app contact@portfolio.example",
        _client("https://data.sec.gov", respond),
    )
    assert client.get_company_facts(1234)["entityName"] == "Example"
    assert seen[0].url.path.endswith("CIK0000001234.json")


def test_contracts_finder_public_search_passes_cursor() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cursor"] == "next-page"
        return httpx.Response(200, json={"releases": [{"id": "release-1"}]})

    client = ContractsFinderOCDSClient(
        _client("https://www.contractsfinder.service.gov.uk", respond)
    )
    result = client.search_releases(
        published_from=date(2026, 1, 1),
        published_to=date(2026, 1, 31),
        cursor="next-page",
    )

    assert result["releases"][0]["id"] == "release-1"
