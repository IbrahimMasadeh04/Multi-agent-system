from enum import Enum
from typing import List, Dict, Any

from pydantic import BaseModel, Field

class IntentEnum(str, Enum):
    QUERY_DATA = "QUERY_DATA"
    UPDATE_DATA = "UPDATE_DATA"
    GREETING = "GREETING"
    UNKNOWN = "UNKNOWN"


class IntentSchema(BaseModel):
    primary_intent: IntentEnum = Field(description="The primary intent of the user (e.g., QUERY_DATA, UPDATE_DATA, GREETING, UNKNOWN).")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted entities like item_name, quantity, price, device_id.")
    domain: str = Field(description="The likely domain (DB, PDF_DOCS, WEB).")
    confidence: float = Field(description="Confidence level of the intent classification (0 to 1).")
    requires_confirmation: bool = Field(description="True if the intent involves changing data (INSERT/UPDATE).")


class PlannerOutput(BaseModel):
    tasks: list[str] = Field(description="List of step-by-step tasks to accomplish the user goal using available workers.")


class ComplexityDecision(BaseModel):
        is_complex: bool = Field(description="True if the query requires multiple steps, comparing multiple items, or complex reasoning. False for simple single-step queries.")


