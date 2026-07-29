from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Payload accepted by the agent endpoint."""

    message: str = Field(min_length=1, description="The user's input")


class AgentResponse(BaseModel):
    """Stable API contract returned by the graph."""

    answer: str
    research: str
