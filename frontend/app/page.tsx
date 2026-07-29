"use client";

import { FormEvent, useState } from "react";

type AgentResponse = { answer: string; research: string };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
      setError("无法连接到后端。请确认 FastAPI 正在 http://localhost:8000 运行。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section>
        <p className="eyebrow">LANGGRAPH AGENT</p>
        <h1>Research Workflow</h1>
        <p className="hint">User Input → Research Node → Output</p>
        <form onSubmit={submit}>
          <label htmlFor="message">你的输入</label>
          <textarea id="message" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="输入一条消息…" rows={5} />
          <button disabled={loading}>{loading ? "处理中…" : "运行 Agent"}</button>
        </form>
        {error && <p className="error">{error}</p>}
        {result && <article><h2>Output</h2><p>{result.answer}</p></article>}
      </section>
    </main>
  );
}
