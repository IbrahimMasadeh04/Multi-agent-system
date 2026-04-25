from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    intent_data: dict | None = None
    next_node: str | None = None
    search_score: float | None = None
    plan: list[str] | None = None
    past_steps: list[str] | None = None
    current_task: str | None = None