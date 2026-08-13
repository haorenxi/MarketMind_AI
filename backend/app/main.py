from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback

from .graph import agent_graph
from .schemas import AgentRequest, AgentResponse

app = FastAPI(title="LangGraph Agent API", version="0.1.0")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://market-mind-ai-peach.vercel.app",
        "https://market-mind-ai-git-main-haorenxi-demo.vercel.app",
        "https://agent.haorenxi.top/"
    ],
    allow_origin_regex=r"https://market-mind(?:-ai)?-[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent", response_model=AgentResponse)
def run_agent(request: AgentRequest) -> AgentResponse:
    try:
        result = agent_graph.invoke({"user_input": request.message})
        score = result.get("score") if isinstance(result, dict) else None
        return AgentResponse(
            answer=result["output"],
            research=result["research"],
            score=score,
            score_status=score.get("score_status") if isinstance(score, dict) else None,
            score_error=score.get("score_error") if isinstance(score, dict) else None,
        )
    except Exception as error:
        logger.exception("Agent execution failed: %s", error)
        logger.error(traceback.format_exc())
        fallback = (
            "# Report Unavailable\n\n"
            "The research workflow failed unexpectedly, but the API stayed up."
        )
        return AgentResponse(answer=fallback, research=fallback, score=None, score_status="fallback_scored", score_error=str(error))
