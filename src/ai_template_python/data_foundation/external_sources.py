"""Typed, bounded clients for public procurement and economic data sources."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class ExternalObservation:
    source_name: str
    series_id: str
    country_code: str
    observed_on: date
    value: Decimal
    unit: str
    currency: str | None
    source_url: str
    retrieved_at: datetime
    source_version: str | None = None


@dataclass(frozen=True, slots=True)
class USASpendingAward:
    award_id: str
    recipient_name: str | None
    award_amount: Decimal | None
    start_date: date | None
    end_date: date | None
    awarding_agency: str | None
    award_type: str | None
    raw_fields: Mapping[str, Any]


class WorldBankIndicatorsClient:
    """Client for the unauthenticated World Bank Indicators API v2."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url="https://api.worldbank.org/v2",
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    def get_indicator(
        self,
        *,
        country_code: str,
        indicator_id: str,
        start_year: int,
        end_year: int,
    ) -> list[ExternalObservation]:
        if start_year > end_year:
            raise ValueError("start_year must be on or before end_year")
        if not re.fullmatch(r"[A-Za-z0-9.;_-]+", country_code):
            raise ValueError("country_code contains unsupported characters")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", indicator_id):
            raise ValueError("indicator_id contains unsupported characters")

        observations: list[ExternalObservation] = []
        page = 1
        retrieved_at = datetime.now(UTC)
        while True:
            response = self._client.get(
                f"/country/{country_code}/indicator/{indicator_id}",
                params={
                    "format": "json",
                    "date": f"{start_year}:{end_year}",
                    "per_page": 1000,
                    "page": page,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != 2:
                raise ValueError("Unexpected World Bank Indicators response")
            metadata, rows = payload
            if not isinstance(metadata, dict) or (rows is not None and not isinstance(rows, list)):
                raise ValueError("Unexpected World Bank Indicators response shape")
            if rows is None:
                rows = []
            for row in rows:
                if not isinstance(row, dict) or row.get("value") is None:
                    continue
                country = row.get("country", {})
                observations.append(
                    ExternalObservation(
                        source_name="world_bank_indicators",
                        series_id=indicator_id,
                        country_code=str(
                            row.get("countryiso3code") or country.get("id") or country_code
                        ),
                        observed_on=date(int(row["date"]), 1, 1),
                        value=Decimal(str(row["value"])),
                        unit=str(row.get("unit") or "indicator units"),
                        currency=None,
                        source_url=(
                            f"https://api.worldbank.org/v2/country/{country_code}/indicator/"
                            f"{indicator_id}?date={start_year}:{end_year}"
                        ),
                        retrieved_at=retrieved_at,
                        source_version=str(metadata.get("lastupdated") or "unknown"),
                    )
                )
            if page >= int(metadata.get("pages", 1)):
                break
            page += 1
        return observations


class FredClient:
    """FRED series observation adapter; the key is required by FRED."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key.strip():
            raise ValueError("FRED_API_KEY is required")
        self._api_key = api_key.strip()
        self._client = client or httpx.Client(
            base_url="https://api.stlouisfed.org/fred",
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    def get_observations(
        self,
        *,
        series_id: str,
        start_date: date,
        end_date: date,
    ) -> list[ExternalObservation]:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if not re.fullmatch(r"[A-Za-z0-9_]+", series_id):
            raise ValueError("series_id contains unsupported characters")

        observations: list[ExternalObservation] = []
        offset = 0
        retrieved_at = datetime.now(UTC)
        while True:
            response = self._client.get(
                "/series/observations",
                params={
                    "api_key": self._api_key,
                    "file_type": "json",
                    "series_id": series_id,
                    "observation_start": start_date.isoformat(),
                    "observation_end": end_date.isoformat(),
                    "limit": 100000,
                    "offset": offset,
                    "sort_order": "asc",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
                raise ValueError("Unexpected FRED observations response")
            for row in payload["observations"]:
                if not isinstance(row, dict) or row.get("value") in (None, "."):
                    continue
                observations.append(
                    ExternalObservation(
                        source_name="fred",
                        series_id=series_id,
                        country_code="USA",
                        observed_on=date.fromisoformat(row["date"]),
                        value=Decimal(row["value"]),
                        unit=str(payload.get("units") or "series units"),
                        currency=None,
                        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                        retrieved_at=retrieved_at,
                        source_version=str(row.get("realtime_end") or "unknown"),
                    )
                )
            offset += len(payload["observations"])
            if offset >= int(payload.get("count", offset)) or not payload["observations"]:
                break
        return observations


class USAspendingClient:
    """Client for filtered USAspending award search (no API key required)."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url="https://api.usaspending.gov/api/v2",
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def search_contract_awards(
        self,
        *,
        start_date: date,
        end_date: date,
        page: int = 1,
        limit: int = 100,
    ) -> list[USASpendingAward]:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if page < 1 or not 1 <= limit <= 100:
            raise ValueError("page must be positive and limit must be between 1 and 100")
        response = self._client.post(
            "/search/spending_by_award/",
            json={
                "filters": {
                    "time_period": [
                        {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
                    ],
                    "award_type_codes": ["A", "B", "C", "D"],
                },
                "fields": [
                    "Award ID",
                    "Recipient Name",
                    "Award Amount",
                    "Start Date",
                    "End Date",
                    "Awarding Agency",
                    "Award Type",
                ],
                "page": page,
                "limit": limit,
                "sort": "Award Amount",
                "order": "desc",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Unexpected USAspending award search response")
        awards: list[USASpendingAward] = []
        for row in payload["results"]:
            if not isinstance(row, dict) or not row.get("Award ID"):
                continue
            amount = row.get("Award Amount")
            awards.append(
                USASpendingAward(
                    award_id=str(row["Award ID"]),
                    recipient_name=row.get("Recipient Name"),
                    award_amount=Decimal(str(amount)) if amount is not None else None,
                    start_date=date.fromisoformat(row["Start Date"])
                    if row.get("Start Date")
                    else None,
                    end_date=date.fromisoformat(row["End Date"]) if row.get("End Date") else None,
                    awarding_agency=row.get("Awarding Agency"),
                    award_type=row.get("Award Type"),
                    raw_fields=row,
                )
            )
        return awards


class SecEdgarClient:
    """Read-only SEC EDGAR company-facts adapter with a declared User-Agent."""

    def __init__(self, user_agent: str, client: httpx.Client | None = None) -> None:
        if not user_agent.strip() or "@" not in user_agent:
            raise ValueError("SEC_USER_AGENT must identify the application and a contact email")
        self._client = client or httpx.Client(
            base_url="https://data.sec.gov",
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    @staticmethod
    def _cik(cik: str | int) -> str:
        digits = str(cik).strip()
        if not digits.isdigit() or len(digits) > 10:
            raise ValueError("CIK must contain one to ten digits")
        return digits.zfill(10)

    def get_company_facts(self, cik: str | int) -> dict[str, Any]:
        response = self._client.get(f"/api/xbrl/companyfacts/CIK{self._cik(cik)}.json")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "facts" not in payload:
            raise ValueError("Unexpected SEC company facts response")
        return payload

    def get_submissions(self, cik: str | int) -> dict[str, Any]:
        response = self._client.get(f"/submissions/CIK{self._cik(cik)}.json")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "filings" not in payload:
            raise ValueError("Unexpected SEC submissions response")
        return payload


class ContractsFinderOCDSClient:
    """Read published Contracts Finder OCDS releases from its public search API."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url="https://www.contractsfinder.service.gov.uk",
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def search_releases(
        self,
        *,
        published_from: date,
        published_to: date,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        if published_from > published_to:
            raise ValueError("published_from must be on or before published_to")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        params: dict[str, str | int] = {
            "publishedFrom": published_from.isoformat(),
            "publishedTo": published_to.isoformat(),
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        response = self._client.get("/Published/Notices/OCDS/Search", params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("releases"), list):
            raise ValueError("Unexpected Contracts Finder OCDS release package")
        return payload
