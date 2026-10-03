"""Framework-independent contracts for investigation tools."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ToolContext:
    investigation_id: str
    tenant_id: str
    requester_id: str
    correlation_id: str
    deadline: datetime


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    source_type: Literal["database", "document", "external"]
    source_id: str
    locator: str
    citation_label: str
    observed_at: datetime
    excerpt: str | None = None
    content_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ToolError:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ToolResult[ToolOutput]:
    data: ToolOutput | None = None
    evidence: tuple[EvidenceRecord, ...] = ()
    error: ToolError | None = None

    def __post_init__(self) -> None:
        if (self.data is None) == (self.error is None):
            raise ValueError("A tool result must contain exactly one of data or error")


class Tool[ToolInput, ToolOutput](Protocol):
    name: str

    async def execute(
        self,
        request: ToolInput,
        /,
        *,
        context: ToolContext,
    ) -> ToolResult[ToolOutput]: ...


@dataclass(frozen=True, slots=True)
class SpendAnalysisRequest:
    start_date: date
    end_date: date
    supplier_id: str | None = None
    category_id: str | None = None
    group_by: Literal["month", "supplier", "category"] = "month"

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")


@dataclass(frozen=True, slots=True)
class SpendPeriod:
    period: str
    amount: Decimal
    currency: str
    transaction_count: int


@dataclass(frozen=True, slots=True)
class SpendAnalysisResult:
    periods: tuple[SpendPeriod, ...]


@dataclass(frozen=True, slots=True)
class DocumentSearchRequest:
    query: str
    document_types: tuple[Literal["contract", "policy", "supplier_profile"], ...]
    top_k: int = 5
    supplier_id: str | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        if not self.document_types:
            raise ValueError("at least one allowed document type is required")
        allowed_types = {"contract", "policy", "supplier_profile"}
        if not set(self.document_types).issubset(allowed_types):
            raise ValueError("document_types contains an unsupported type")


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    document_id: str
    title: str
    excerpt: str
    locator: str
    source_version: str
    relevance: float


@dataclass(frozen=True, slots=True)
class DocumentSearchResult:
    corpus_version: str
    documents: tuple[RetrievedDocument, ...]


@dataclass(frozen=True, slots=True)
class MarketSeriesRequest:
    series_id: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not self.series_id.strip():
            raise ValueError("series_id must not be empty")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")


@dataclass(frozen=True, slots=True)
class MarketDataPoint:
    observed_on: date
    value: Decimal
    unit: str


@dataclass(frozen=True, slots=True)
class MarketSeriesResult:
    series_id: str
    source: str
    retrieved_at: datetime
    points: tuple[MarketDataPoint, ...]


@dataclass(frozen=True, slots=True)
class VarianceAnalysisRequest:
    baseline: Decimal
    current: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.baseline == 0:
            raise ValueError("baseline must be non-zero to calculate percentage change")
        if not self.currency.strip():
            raise ValueError("currency must not be empty")


@dataclass(frozen=True, slots=True)
class VarianceAnalysisResult:
    absolute_change: Decimal
    percentage_change: Decimal
    currency: str


SpendAnalysisTool = Tool[SpendAnalysisRequest, SpendAnalysisResult]
DocumentSearchTool = Tool[DocumentSearchRequest, DocumentSearchResult]
MarketSeriesTool = Tool[MarketSeriesRequest, MarketSeriesResult]
VarianceAnalysisTool = Tool[VarianceAnalysisRequest, VarianceAnalysisResult]
