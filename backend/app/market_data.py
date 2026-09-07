"""Structured market data models and deterministic calculations."""

from __future__ import annotations

from enum import Enum
import re
from typing import Literal

from pydantic import BaseModel, Field


class ResearchType(str, Enum):
    comprehensive = "comprehensive"
    market_size = "market_size"
    competitor = "competitor"
    product_price = "product_price"
    customer_demand = "customer_demand"
    supply_chain = "supply_chain"
    market_entry = "market_entry"


class MarketMetric(BaseModel):
    metric_name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    currency: str | None = None
    geography: str | None = None
    period: str = Field(min_length=1)
    segment: str | None = None
    company: str | None = None
    source_url: str = ""
    source_title: str = ""
    source_excerpt: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    is_forecast: bool = False


class CalculatedMetric(BaseModel):
    metric_name: str
    value: float
    unit: str
    start_period: str | None = None
    end_period: str | None = None
    geography: str | None = None
    segment: str | None = None
    inputs: list[float] = Field(default_factory=list)


class TimeSeriesPoint(BaseModel):
    period: str
    value: float
    unit: str
    currency: str | None = None
    geography: str | None = None
    segment: str | None = None
    source_url: str = ""
    is_forecast: bool = False


class CompetitorRecord(BaseModel):
    company: str
    market_share: float | None = None
    revenue: float | None = None
    revenue_currency: str | None = None
    product_focus: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class MarketExtraction(BaseModel):
    metrics: list[MarketMetric] = Field(default_factory=list)
    competitors: list[CompetitorRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ClaimValidation(BaseModel):
    claim: str
    status: Literal["verified", "warning", "failed"]
    source_urls: list[str] = Field(default_factory=list)
    citation_present: bool
    source_supports_claim: bool
    cross_source_verified: bool = False
    numeric_consistent: bool = True
    applicability: str
    confidence: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    accuracy_score: int = Field(ge=0, le=100)
    applicability_score: int = Field(ge=0, le=100)
    citation_coverage: float = Field(ge=0, le=1)
    cross_source_rate: float = Field(ge=0, le=1)
    status: Literal["pass", "warning", "fail"]
    applicability: str
    claims: list[ClaimValidation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    """Return CAGR as a percentage."""

    if start_value <= 0 or end_value < 0:
        raise ValueError("CAGR values must be positive")
    if years <= 0:
        raise ValueError("CAGR years must be positive")
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def _year(period: str) -> int | None:
    digits = "".join(character for character in period if character.isdigit())
    if len(digits) < 4:
        return None
    value = int(digits[:4])
    return value if 1900 <= value <= 2200 else None


def analyze_market_metrics(
    metrics: list[MarketMetric],
) -> tuple[list[MarketMetric], list[CalculatedMetric], list[TimeSeriesPoint], list[str]]:
    """Deduplicate metrics and derive safe, reproducible market calculations."""

    unique: dict[tuple[object, ...], MarketMetric] = {}
    for metric in metrics:
        key = (
            metric.metric_name.lower(),
            metric.period,
            metric.geography,
            metric.segment,
            metric.company,
            metric.source_url,
            metric.value,
        )
        unique.setdefault(key, metric)
    normalized = list(unique.values())

    time_series = [
        TimeSeriesPoint(
            period=item.period,
            value=item.value,
            unit=item.unit,
            currency=item.currency,
            geography=item.geography,
            segment=item.segment,
            source_url=item.source_url,
            is_forecast=item.is_forecast,
        )
        for item in normalized
        if item.metric_name.lower() == "market_size" and _year(item.period) is not None
    ]
    time_series.sort(key=lambda item: _year(item.period) or 0)

    calculated: list[CalculatedMetric] = []
    warnings: list[str] = []
    groups: dict[tuple[object, ...], list[MarketMetric]] = {}
    for item in normalized:
        if item.metric_name.lower() != "market_size" or _year(item.period) is None:
            continue
        key = (item.unit.lower(), item.currency, item.geography, item.segment)
        groups.setdefault(key, []).append(item)

    for (unit, _currency, geography, segment), items in groups.items():
        ordered = sorted(items, key=lambda item: _year(item.period) or 0)
        first, last = ordered[0], ordered[-1]
        years = (_year(last.period) or 0) - (_year(first.period) or 0)
        if years <= 0 or first.value <= 0:
            continue
        try:
            value = round(calculate_cagr(first.value, last.value, years), 2)
        except ValueError:
            continue
        calculated.append(
            CalculatedMetric(
                metric_name="cagr",
                value=value,
                unit="percent",
                start_period=first.period,
                end_period=last.period,
                geography=geography,
                segment=segment,
                inputs=[first.value, last.value],
            )
        )

    if normalized and not calculated:
        warnings.append("没有找到口径一致的两个年度市场规模数据，因此未计算 CAGR。")
    if any(not item.source_url for item in normalized):
        warnings.append("部分结构化指标缺少来源 URL，不能视为已验证事实。")
    return normalized, calculated, time_series, warnings


def validate_market_data(
    metrics: list[MarketMetric],
    evidence: list[dict],
) -> ValidationResult:
    """Apply deterministic citation and applicability checks to market metrics."""

    if not metrics:
        return ValidationResult(
            accuracy_score=0,
            applicability_score=0,
            citation_coverage=0,
            cross_source_rate=0,
            status="warning",
            applicability="未提取到结构化市场指标，报告只能作为探索性资料使用。",
            warnings=["未提取到可校验的数值指标。", "当前数据来自搜索摘要，尚未进行网页全文核验。"],
        )

    evidence_by_url = {
        str(item.get("url", "")).strip(): " ".join(
            str(item.get(field, "")) for field in ("content", "snippet", "title")
        )
        for item in evidence
        if str(item.get("url", "")).strip()
    }

    def number_appears(item: MarketMetric) -> bool:
        source_text = f"{evidence_by_url.get(item.source_url, '')} {item.source_excerpt}".lower()
        candidates = {str(item.value), f"{item.value:g}", f"{item.value:,.1f}", f"{item.value:,.2f}"}
        return any(re.search(rf"(?<!\d){re.escape(candidate)}(?!\d)", source_text) for candidate in candidates)

    cited = sum(bool(item.source_url) for item in metrics)
    supported = sum(bool(item.source_url in evidence_by_url and number_appears(item)) for item in metrics)

    group_sources: dict[tuple[object, ...], set[str]] = {}
    for item in metrics:
        key = (item.metric_name.lower(), item.period, item.geography, item.segment)
        if item.source_url:
            group_sources.setdefault(key, set()).add(item.source_url)
    cross_verified: set[tuple[object, ...]] = set()
    conflicting: set[tuple[object, ...]] = set()
    for key, urls in group_sources.items():
        values = [
            item.value
            for item in metrics
            if (item.metric_name.lower(), item.period, item.geography, item.segment) == key
        ]
        if len(urls) < 2 or not values:
            continue
        relative_difference = (max(values) - min(values)) / max(abs(max(values)), 1e-9)
        if relative_difference <= 0.1:
            cross_verified.add(key)
        elif relative_difference > 0.2:
            conflicting.add(key)

    claims: list[ClaimValidation] = []
    scope_complete = 0
    for item in metrics:
        key = (item.metric_name.lower(), item.period, item.geography, item.segment)
        citation_present = bool(item.source_url)
        source_supports = bool(item.source_url in evidence_by_url and number_appears(item))
        if item.metric_name.lower() == "market_size":
            complete = bool(item.period and item.geography)
        elif item.metric_name.lower() in {"market_share", "revenue"}:
            complete = bool(item.period and item.company)
        else:
            complete = bool(item.period and (item.geography or item.company or item.segment))
        scope_complete += int(complete)
        issues: list[str] = []
        if not citation_present:
            issues.append("缺少来源 URL")
        elif not source_supports:
            issues.append("来源摘要中未找到与该指标一致的数值，尚不能确认来源支持")
        if key in conflicting:
            issues.append("多个来源的数值差异超过 20%，可能存在统计口径冲突")
        elif key not in cross_verified:
            issues.append("关键指标尚未获得两个独立来源支持")
        if not complete:
            issues.append("适用地区、公司或细分市场信息不完整")
        status: Literal["verified", "warning", "failed"] = "verified"
        if not citation_present or not source_supports:
            status = "failed"
        elif issues:
            status = "warning"
        scope = ", ".join(filter(None, [item.geography, item.segment, item.company, item.period]))
        claims.append(
            ClaimValidation(
                claim=f"{item.metric_name}: {item.value} {item.unit}",
                status=status,
                source_urls=[item.source_url] if item.source_url else [],
                citation_present=citation_present,
                source_supports_claim=source_supports,
                cross_source_verified=key in cross_verified,
                numeric_consistent=source_supports and key not in conflicting,
                applicability=scope or "适用范围不完整",
                confidence=item.confidence,
                issues=issues,
            )
        )

    citation_coverage = cited / len(metrics)
    support_rate = supported / len(metrics)
    cross_source_rate = len(cross_verified) / max(len(group_sources), 1)
    scope_rate = scope_complete / len(metrics)
    accuracy = round((citation_coverage * 0.4 + support_rate * 0.4 + cross_source_rate * 0.2) * 100)
    applicability_score = round(scope_rate * 100)
    if accuracy >= 85 and applicability_score >= 80:
        status = "pass"
    elif accuracy < 50 or applicability_score < 50:
        status = "fail"
    else:
        status = "warning"
    return ValidationResult(
        accuracy_score=accuracy,
        applicability_score=applicability_score,
        citation_coverage=round(citation_coverage, 3),
        cross_source_rate=round(cross_source_rate, 3),
        status=status,
        applicability="结论仅适用于每条指标标注的地区、时期和细分市场；预测值不代表实际结果。",
        claims=claims,
        warnings=["当前数据来自搜索摘要，准确性评分不等于网页全文或人工事实核验。"],
    )
