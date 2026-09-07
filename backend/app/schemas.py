from pydantic import BaseModel, Field

from .market_data import (
    CalculatedMetric,
    CompetitorRecord,
    MarketMetric,
    ResearchType,
    TimeSeriesPoint,
    ValidationResult,
)


class AgentRequest(BaseModel):
    """Payload accepted by the agent endpoint."""

    message: str = Field(min_length=1, description="The user's input")
    research_type: ResearchType = ResearchType.comprehensive


class AgentResponse(BaseModel):
    """Stable API contract returned by the graph."""

    answer: str
    research: str
    score: dict | None = None
    score_status: str | None = None
    score_error: str | None = None
    research_type: ResearchType = ResearchType.comprehensive
    metrics: list[MarketMetric] = Field(default_factory=list)
    calculated_metrics: list[CalculatedMetric] = Field(default_factory=list)
    time_series: list[TimeSeriesPoint] = Field(default_factory=list)
    competitors: list[CompetitorRecord] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: ValidationResult | None = None
