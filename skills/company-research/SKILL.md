---
name: company-research
description: Research companies, markets, competitors, products, supply chains, technologies, papers, and open-source ecosystems, then produce a sourced report that separates facts, analysis, and recommendations. Use for current market-intelligence work; do not use for requests that only need copywriting or a summary of user-provided material.
---

# Company Research

Produce decision-ready research grounded in current, traceable evidence.

## Workflow

1. Clarify the decision or question the research must support. Infer reasonable scope from the request; ask only when geography, time range, comparison set, or intended decision would materially change the result.
2. Classify the work as company, competitor, product, market, supply-chain, technology, paper, open-source ecosystem, or a combination. For detailed coverage guidance, read [research modes](references/research-modes.md) only when the mode needs it.
3. Build a compact evidence plan. Identify the claims that must be established, suitable source types, useful searches, and a stopping condition.
4. Search for current external evidence when claims are time-sensitive or not supported by material supplied by the user. Prefer primary and authoritative sources. Read [evidence standards](references/evidence-standards.md) when sources conflict, evidence is weak, or the decision is consequential.
5. Normalize evidence by claim and URL, remove duplicates, preserve publication or event dates when relevant, and distinguish a source statement from an inference based on it.
6. Synthesize the report using the output contract below. Do not copy search-result snippets as analysis.
7. Review the report against [the scoring rubric](references/scoring-rubric.md) when the task requests scoring, the report informs a meaningful decision, or evidence quality is uneven. Revise material weaknesses once rather than endlessly expanding scope.

## Tool use

- Use available web or connected-source tools for current facts. Cite the final supporting page, not a search-results page.
- Do not invent access to paid databases or private company information.
- Treat source snippets as discovery aids; open the underlying source before relying on a material claim when possible.
- Stop searching when the required claims have adequate support or when further search is unlikely to resolve a documented evidence gap.

## Output contract

Use this stable top-level structure unless the user requests another format:

```markdown
# <specific report title>
## Facts
## Analysis
## Recommendations
## Sources
```

- **Facts:** verifiable claims with nearby source links. State dates, geography, units, definitions, and uncertainty when they affect interpretation.
- **Analysis:** patterns, comparisons, implications, and confidence levels derived from the facts. Label inference clearly.
- **Recommendations:** specific actions, priorities, risks, triggers, or next checks tied to the analysis. Do not add recommendations when the user requested descriptive research only.
- **Sources:** a deduplicated list of the most useful sources. Preserve titles and direct URLs.

Prefer concise paragraphs, bullets, and comparison tables. Do not promote an unverified claim into Facts. When evidence is insufficient or contradictory, say what is unknown and why.

## Application integration

When this skill is loaded inside the MarketMind LangGraph application, treat the supplied plan, current step, collected evidence, and search limit as execution state. Follow that state rather than restarting the workflow. The application owns routing, retries, API behavior, and deployment; this skill owns research decisions and output quality.
