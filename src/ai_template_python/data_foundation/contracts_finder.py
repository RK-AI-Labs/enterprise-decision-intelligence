"""Streaming parser for published Contracts Finder FullNotice XML exports."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

type JsonScalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class ContractAward:
    award_id: str | None
    supplier_name: str | None
    supplier_reference: str | None
    awarded_value_gbp: Decimal | None
    start_date: datetime | None
    end_date: datetime | None
    awarded_date: datetime | None


@dataclass(frozen=True, slots=True)
class ContractNotice:
    source_notice_id: str
    identifier: str | None
    title: str
    description: str | None
    status: str | None
    organisation_name: str | None
    cpv_description: str | None
    notice_type: str | None
    published_at: datetime | None
    deadline_at: datetime | None
    contract_start: datetime | None
    contract_end: datetime | None
    value_low_gbp: Decimal | None
    value_high_gbp: Decimal | None
    region: str | None
    postcode: str | None
    awards: tuple[ContractAward, ...]
    raw_notice: Mapping[str, JsonScalar]


def _text(element: ElementTree.Element, name: str) -> str | None:
    value = element.findtext(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Invalid Contracts Finder decimal value: {value!r}") from error


def _datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid Contracts Finder datetime value: {value!r}") from error


def _parse_award(element: ElementTree.Element) -> ContractAward:
    return ContractAward(
        award_id=_text(element, "Id"),
        supplier_name=_text(element, "SupplierName"),
        supplier_reference=_text(element, "Reference"),
        awarded_value_gbp=_decimal(_text(element, "Value")),
        start_date=_datetime(_text(element, "StartDate")),
        end_date=_datetime(_text(element, "EndDate")),
        awarded_date=_datetime(_text(element, "AwardedDate")),
    )


def iter_contracts_finder_notices(path: str | Path) -> Iterator[ContractNotice]:
    """Yield normalized notices from a Contracts Finder XML export.

    Uses ``iterparse`` so memory use does not grow with the export size. The
    source ID, raw notice fields, and award details are retained for provenance.
    """
    for _, element in ElementTree.iterparse(path, events=("end",)):
        if element.tag != "FullNotice":
            continue

        notice = element.find("Notice")
        if notice is None:
            raise ValueError("Contracts Finder FullNotice is missing its Notice element")

        source_notice_id = _text(notice, "Id") or _text(element, "Id")
        if source_notice_id is None:
            raise ValueError("Contracts Finder notice is missing its stable ID")

        raw_notice = {
            child.tag: (
                ElementTree.tostring(child, encoding="unicode") if len(child) else child.text
            )
            for child in notice
            if child.tag != "ContactDetails"
        }
        awards_element = element.find("Awards")
        awards = (
            tuple(_parse_award(award) for award in awards_element.findall("AwardDetail"))
            if awards_element is not None
            else ()
        )
        title = _text(notice, "Title") or _text(notice, "Identifier") or source_notice_id

        yield ContractNotice(
            source_notice_id=source_notice_id,
            identifier=_text(notice, "Identifier"),
            title=title,
            description=_text(notice, "Description"),
            status=_text(notice, "Status"),
            organisation_name=_text(notice, "OrganisationName"),
            cpv_description=_text(notice, "CpvDescription"),
            notice_type=_text(notice, "Type"),
            published_at=_datetime(_text(notice, "PublishedDate")),
            deadline_at=_datetime(_text(notice, "DeadlineDate")),
            contract_start=_datetime(_text(notice, "Start")),
            contract_end=_datetime(_text(notice, "End")),
            value_low_gbp=_decimal(_text(notice, "ValueLow")),
            value_high_gbp=_decimal(_text(notice, "ValueHigh")),
            region=_text(notice, "Region"),
            postcode=_text(notice, "Postcode"),
            awards=awards,
            raw_notice=raw_notice,
        )
        element.clear()
