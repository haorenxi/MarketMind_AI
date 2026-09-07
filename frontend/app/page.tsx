"use client";

import type { ReactNode } from "react";
import { FormEvent, useMemo, useState } from "react";

type Score = {
  score: number;
  dimension_scores: Record<string, number>;
  issues: string[];
  improvement_suggestions: string[];
  pass_or_fail: string;
};

type MarketMetric = {
  metric_name: string;
  value: number;
  unit: string;
  currency?: string | null;
  geography?: string | null;
  period: string;
  segment?: string | null;
  source_url: string;
  is_forecast: boolean;
};

type CalculatedMetric = {
  metric_name: string;
  value: number;
  unit: string;
  start_period?: string | null;
  end_period?: string | null;
};

type TimeSeriesPoint = {
  period: string;
  value: number;
  unit: string;
  currency?: string | null;
  is_forecast: boolean;
};

type Competitor = {
  company: string;
  market_share?: number | null;
  revenue?: number | null;
  revenue_currency?: string | null;
  product_focus: string[];
  strengths: string[];
  source_urls: string[];
};

type Validation = {
  accuracy_score: number;
  applicability_score: number;
  citation_coverage: number;
  cross_source_rate: number;
  status: string;
  applicability: string;
  claims: Array<{
    claim: string;
    status: string;
    applicability: string;
    source_urls: string[];
    issues: string[];
  }>;
  warnings: string[];
};

type AgentResponse = {
  answer: string;
  research: string;
  research_type: string;
  score?: Score | null;
  metrics: MarketMetric[];
  calculated_metrics: CalculatedMetric[];
  time_series: TimeSeriesPoint[];
  competitors: Competitor[];
  warnings: string[];
  validation?: Validation | null;
};

type ReportSection = {
  title: string;
  content: string;
};

type SourceItem = {
  title: string;
  url: string;
  source?: string;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInlineMarkdown(text: string) {
  const escaped = escapeHtml(text);
  const withLinks = escaped.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>',
  );
  const withBold = withLinks.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  const withCode = withBold.replace(/`([^`]+)`/g, "<code>$1</code>");
  return { __html: withCode };
}

function splitSection(markdown: string, heading: string): string {
  const pattern = new RegExp(`^##\\s+${heading}\\s*$`, "mi");
  const startMatch = markdown.match(pattern);
  if (!startMatch || startMatch.index === undefined) return "";

  const start = startMatch.index + startMatch[0].length;
  const rest = markdown.slice(start);
  const nextHeading = rest.search(/^##\s+/m);
  return (nextHeading >= 0 ? rest.slice(0, nextHeading) : rest).trim();
}

function extractReportSections(markdown: string) {
  return {
    facts: splitSection(markdown, "Facts"),
    analysis: splitSection(markdown, "Analysis"),
    recommendations: splitSection(markdown, "Recommendations"),
    sources: splitSection(markdown, "Sources"),
  };
}

function parseSourceItems(markdown: string): SourceItem[] {
  const sourcesBlock = splitSection(markdown, "Sources");
  if (!sourcesBlock) return [];

  return sourcesBlock
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => {
      const linkMatch = line.match(/- \[([^\]]+)\]\((https?:\/\/[^)]+)\)(?:\s*-\s*(.+))?/);
      if (linkMatch) {
        return {
          title: linkMatch[1],
          url: linkMatch[2],
          source: linkMatch[3] || "",
        };
      }

      const plainMatch = line.match(/- (.+?)(?:\s*\((https?:\/\/[^)]+)\))?/);
      return {
        title: plainMatch?.[1] ?? line.replace(/^- /, ""),
        url: plainMatch?.[2] ?? "",
      };
    })
    .filter((item) => Boolean(item.url));
}

function renderMarkdownBlock(markdown: string) {
  if (!markdown.trim()) {
    return <p className="hint">No content returned.</p>;
  }

  const lines = markdown.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (line.startsWith("### ")) {
      blocks.push(
        <h3 key={`h3-${blocks.length}`} className="md-h3">
          {line.slice(4)}
        </h3>,
      );
      i += 1;
      continue;
    }

    if (line.startsWith("# ")) {
      blocks.push(
        <h1 key={`h1-${blocks.length}`} className="md-h1">
          {line.slice(2)}
        </h1>,
      );
      i += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) {
        items.push(lines[i].slice(2));
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="md-ul">
          {items.map((item, index) => (
            <li key={`${item}-${index}`} dangerouslySetInnerHTML={renderInlineMarkdown(item)} />
          ))}
        </ul>,
      );
      continue;
    }

    blocks.push(
      <p key={`p-${blocks.length}`} className="md-p" dangerouslySetInnerHTML={renderInlineMarkdown(line)} />,
    );
    i += 1;
  }

  return blocks;
}

function ReportSectionCard({ title, content }: ReportSection) {
  return (
    <section className="section-card">
      <div className="section-card__header">
        <h2>{title}</h2>
      </div>
      <div className="markdown-body">{renderMarkdownBlock(content)}</div>
    </section>
  );
}

function TrendChart({ points }: { points: TimeSeriesPoint[] }) {
  if (points.length < 2) return <p className="hint">至少需要两个同口径年度数据点才能绘制趋势。</p>;
  const width = 720;
  const height = 240;
  const padding = 36;
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coordinates = points.map((point, index) => ({
    ...point,
    x: padding + (index * (width - padding * 2)) / Math.max(points.length - 1, 1),
    y: height - padding - ((point.value - min) / span) * (height - padding * 2),
  }));

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="市场规模趋势图">
        <polyline
          points={coordinates.map((point) => `${point.x},${point.y}`).join(" ")}
          fill="none"
          stroke="#72d6b1"
          strokeWidth="4"
        />
        {coordinates.map((point) => (
          <g key={`${point.period}-${point.value}`}>
            <circle cx={point.x} cy={point.y} r="6" fill={point.is_forecast ? "#f6c177" : "#63b3ed"} />
            <text x={point.x} y={point.y - 14} textAnchor="middle">{point.value}</text>
            <text x={point.x} y={height - 10} textAnchor="middle">{point.period}</text>
          </g>
        ))}
      </svg>
      <p className="chart-caption">蓝色为历史数据，黄色为预测数据；单位：{points[0].unit}</p>
    </div>
  );
}

export default function Home() {
  const [message, setMessage] = useState("");
  const [researchType, setResearchType] = useState("comprehensive");
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, research_type: researchType }),
      });
      if (!response.ok) throw new Error("Agent request failed");
      setResult(await response.json());
    } catch {
      setError("Unable to reach the backend. Please verify the API address and try again.");
    } finally {
      setLoading(false);
    }
  }

  const reportSections = useMemo(() => {
    if (!result?.answer) return null;
    return extractReportSections(result.answer);
  }, [result]);

  const sourceItems = useMemo(() => {
    if (!result?.answer) return [];
    return parseSourceItems(result.answer);
  }, [result]);

  const scoreItems = useMemo(() => {
    if (!result?.score) return [];
    return Object.entries(result.score.dimension_scores);
  }, [result]);

  const latestMarketSize = useMemo(() => {
    const candidates = (result?.metrics ?? []).filter((item) => item.metric_name === "market_size");
    return candidates.sort((a, b) => b.period.localeCompare(a.period))[0];
  }, [result]);

  const cagr = result?.calculated_metrics.find((item) => item.metric_name === "cagr");

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">LANGGRAPH AGENT</p>
          <h1>Research Workflow</h1>
          <p className="hint">User Input → Planner → Research → Report → Score</p>
        </div>

        <form onSubmit={submit} className="input-panel">
          <div className="input-grid">
            <div>
              <label htmlFor="message">研究主题</label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="例如：分析 2022—2026 年中国工业相机市场"
                rows={5}
              />
            </div>
            <div>
              <label htmlFor="research-type">调研类型</label>
              <select id="research-type" value={researchType} onChange={(e) => setResearchType(e.target.value)}>
                <option value="comprehensive">综合市场调研</option>
                <option value="market_size">市场规模与趋势</option>
                <option value="competitor">竞品分析</option>
                <option value="product_price">产品与价格</option>
                <option value="customer_demand">用户需求</option>
                <option value="supply_chain">产业链分析</option>
                <option value="market_entry">市场进入机会</option>
              </select>
              <p className="hint">选择项会控制搜索计划、数据字段和报告结构。</p>
            </div>
          </div>
          <button disabled={loading}>{loading ? "Running..." : "Run Agent"}</button>
        </form>

        {error && <p className="error">{error}</p>}

        {result && (
          <div className="results-grid">
            <div className="report-stack">
              <section className="kpi-grid">
                <article className="kpi-card">
                  <span>最新市场规模</span>
                  <strong>{latestMarketSize ? `${latestMarketSize.value} ${latestMarketSize.currency ?? ""} ${latestMarketSize.unit}` : "暂无数据"}</strong>
                  <small>{latestMarketSize?.period ?? "—"}</small>
                </article>
                <article className="kpi-card">
                  <span>计算 CAGR</span>
                  <strong>{cagr ? `${cagr.value}%` : "暂无数据"}</strong>
                  <small>{cagr ? `${cagr.start_period}—${cagr.end_period}` : "需要两个年度数据点"}</small>
                </article>
                <article className="kpi-card">
                  <span>结构化指标</span>
                  <strong>{result.metrics.length}</strong>
                  <small>可追溯数值记录</small>
                </article>
                <article className="kpi-card">
                  <span>准确度</span>
                  <strong>{result.validation ? `${result.validation.accuracy_score}/100` : "未校验"}</strong>
                  <small>{result.validation?.status ?? "—"}</small>
                </article>
              </section>

              <article className="section-card">
                <div className="section-card__header"><h2>市场趋势</h2></div>
                <TrendChart points={result.time_series} />
              </article>

              {result.competitors.length > 0 && (
                <article className="section-card">
                  <div className="section-card__header"><h2>竞品对比</h2></div>
                  <div className="md-table-wrap">
                    <table className="md-table">
                      <thead><tr><th>公司</th><th>市场份额</th><th>产品方向</th><th>优势</th></tr></thead>
                      <tbody>
                        {result.competitors.map((item) => (
                          <tr key={item.company}>
                            <td>{item.company}</td>
                            <td>{item.market_share == null ? "—" : `${item.market_share}%`}</td>
                            <td>{item.product_focus.join("、") || "—"}</td>
                            <td>{item.strengths.join("、") || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              )}

              <article className="result-card">
                <h2>Report Summary</h2>
                <div className="markdown-body">{renderMarkdownBlock(result.answer)}</div>
              </article>

              {reportSections && (
                <>
                  <ReportSectionCard title="Facts" content={reportSections.facts} />
                  <ReportSectionCard title="Analysis" content={reportSections.analysis} />
                  <ReportSectionCard title="Recommendations" content={reportSections.recommendations} />
                </>
              )}

              {sourceItems.length > 0 && (
                <article className="section-card">
                  <div className="section-card__header">
                    <h2>Sources</h2>
                  </div>
                  <div className="source-list">
                    {sourceItems.map((item) => (
                      <a key={item.url} href={item.url} target="_blank" rel="noreferrer" className="source-card">
                        <strong>{item.title}</strong>
                        <span>{item.url}</span>
                        {item.source ? <small>{item.source}</small> : null}
                      </a>
                    ))}
                  </div>
                </article>
              )}
            </div>

            <aside className="score-card">
              <div className="validation-panel">
                <h2>准确度与适用范围</h2>
                {result.validation ? (
                  <>
                    <div className="score-row"><span>引用覆盖率</span><strong>{Math.round(result.validation.citation_coverage * 100)}%</strong></div>
                    <div className="score-row"><span>多源验证率</span><strong>{Math.round(result.validation.cross_source_rate * 100)}%</strong></div>
                    <div className="score-row"><span>范围完整度</span><strong>{result.validation.applicability_score}%</strong></div>
                    <p className="hint">{result.validation.applicability}</p>
                    {result.validation.claims.length > 0 && (
                      <div className="claim-list">
                        {result.validation.claims.map((claim, index) => (
                          <article className={`claim-card claim-${claim.status}`} key={`${claim.claim}-${index}`}>
                            <strong>{claim.claim}</strong>
                            <small>适用范围：{claim.applicability}</small>
                            {claim.issues.map((issue) => <span key={issue}>{issue}</span>)}
                            {claim.source_urls[0] && <a href={claim.source_urls[0]} target="_blank" rel="noreferrer">查看来源</a>}
                          </article>
                        ))}
                      </div>
                    )}
                    {[...result.warnings, ...result.validation.warnings].length > 0 && (
                      <ul className="warning-list">
                        {[...new Set([...result.warnings, ...result.validation.warnings])].map((warning) => <li key={warning}>{warning}</li>)}
                      </ul>
                    )}
                  </>
                ) : <p className="hint">没有返回校验结果。</p>}
              </div>
              <h2>Score</h2>
              {result.score ? (
                <>
                  <div className="score-ring">
                    <span>{result.score.score}</span>
                    <small>100</small>
                  </div>
                  <p className={`score-badge score-${result.score.pass_or_fail}`}>
                    {result.score.pass_or_fail}
                  </p>
                  <div className="score-list">
                    {scoreItems.map(([key, value]) => (
                      <div key={key} className="score-row">
                        <span>{key}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                  {result.score.issues.length > 0 && (
                    <div className="score-notes">
                      <h3>Issues</h3>
                      <ul>
                        {result.score.issues.map((issue) => (
                          <li key={issue}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <p className="hint">No score returned yet.</p>
              )}
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
