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

type AgentResponse = { answer: string; research: string; score?: Score | null };

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

export default function Home() {
  const [message, setMessage] = useState("");
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
        body: JSON.stringify({ message }),
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

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">LANGGRAPH AGENT</p>
          <h1>Research Workflow</h1>
          <p className="hint">User Input → Planner → Research → Report → Score</p>
        </div>

        <form onSubmit={submit} className="input-panel">
          <label htmlFor="message">Your request</label>
          <textarea
            id="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Analyze the robot vision sensor market"
            rows={6}
          />
          <button disabled={loading}>{loading ? "Running..." : "Run Agent"}</button>
        </form>

        {error && <p className="error">{error}</p>}

        {result && (
          <div className="results-grid">
            <div className="report-stack">
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
