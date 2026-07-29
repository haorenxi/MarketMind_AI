from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .graph import agent_graph
from .schemas import AgentRequest, AgentResponse

app = FastAPI(title="LangGraph Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
        return AgentResponse(answer=result["output"], research=result["research"])
    except Exception as error:
        fallback = (
            "# Report Unavailable\n\n"
            "The research workflow failed unexpectedly, but the API stayed up."
        )
        return AgentResponse(answer=fallback, research=fallback)
