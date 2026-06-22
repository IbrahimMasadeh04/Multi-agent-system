from enum import Enum
from typing import List, Dict, Any

from pydantic import BaseModel, Field

class IntentEnum(str, Enum):
    QUERY_DATA = "QUERY_DATA"
    UPDATE_DATA = "UPDATE_DATA"
    GREETING = "GREETING"
    GENERATE_FILE = "GENERATE_FILE"
    UNKNOWN = "UNKNOWN"


class IntentSchema(BaseModel):
    primary_intent: IntentEnum = Field(description="The primary intent of the user (e.g., QUERY_DATA, UPDATE_DATA, GREETING, GENERATE_FILE, UNKNOWN).")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted entities like item_name, quantity, price, device_id.")
    domain: str = Field(description="The likely domain (DB, PDF_DOCS, WEB).")
    confidence: float = Field(description="Confidence level of the intent classification (0 to 1).")
    requires_confirmation: bool = Field(description="True if the intent involves changing data (CREATE/INSERT/UPDATE).")
    is_complex: bool = Field(default=False, description="True if the query requires multiple distinct steps, actions or retrieving multiple different pieces of information.")


class PlannerOutput(BaseModel):
    tasks: list[str] = Field(description="List of step-by-step tasks to accomplish the user goal using available workers.")


class ComplexityDecision(BaseModel):
        is_complex: bool = Field(description="True if the query requires multiple steps, comparing multiple items, or complex reasoning. False for simple single-step queries.")

from typing import Literal

class RouterDecision(BaseModel):
    next_node: Literal['planner', 'db_analyst', 'internal_search', 'external_search', 'file_generator', 'synthesizer'] = Field(
        description="The next node to execute based on the current context."
    )
    reasoning: str = Field(description="A brief explanation of why this node was chosen.")


class FileGenRouterDecision(BaseModel):
    next_node: Literal[
        'template_manager',
        'template_filler',
        'template_qa',
        'template_generator',
        'agent_orchestrator',
        'done'
    ] = Field(description="The next file generation sub-agent to execute.")
    reasoning: str = Field(description="A brief explanation of why this sub-agent was chosen.")


class TemplateManagerDecision(BaseModel):
    tool_name: Literal[
        'filegen_list_templates',
        'filegen_get_template',
        'filegen_upload_template'
    ] = Field(description="The MCP tool to call. Use 'filegen_list_templates' to browse/list available templates, 'filegen_get_template' to retrieve details of a specific template by ID, 'filegen_upload_template' to upload a new template.")
    template_id: str | None = Field(default=None, description="The template ID (UUID) required by filegen_get_template. Must be provided when tool_name is 'filegen_get_template'. Extract from the conversation context or user query.")
    reasoning: str = Field(description="A brief explanation of why this tool was chosen and how arguments were determined.")


class TemplateFillerDecision(BaseModel):
    tool_name: Literal[
        'filegen_fill_template',
        'filegen_fill_preview',
        'filegen_fill_history',
        'filegen_get_version'
    ] = Field(description="The MCP tool to call. Use 'filegen_fill_template' to fill a template with company data, 'filegen_fill_preview' to preview a filled template, 'filegen_fill_history' to get fill history for a template, 'filegen_get_version' to get a specific version of a filled template.")
    template_id: str | None = Field(default=None, description="The template ID (UUID). Required for all tools. Extract from the conversation context or user query.")
    company_data: str | None = Field(default=None, description="JSON string of company data for filling. Required by filegen_fill_template and filegen_fill_preview. Extract from user query or context.")
    version_id: str | None = Field(default=None, description="The version ID. Required only by filegen_get_version.")
    reasoning: str = Field(description="A brief explanation of why this tool was chosen and how arguments were determined.")


class TemplateQADecision(BaseModel):
    tool_name: Literal[
        'filegen_ask_question',
        'filegen_qa_history',
        'filegen_qa_search'
    ] = Field(description="The MCP tool to call. Use 'filegen_ask_question' to ask a RAG-based question about a template, 'filegen_qa_history' to get Q&A history for a template, 'filegen_qa_search' to search within a template's content.")
    template_id: str | None = Field(default=None, description="The template ID (UUID). Required for all tools. Extract from the conversation context or user query.")
    question: str | None = Field(default=None, description="The question to ask about the template. Required by filegen_ask_question. Use the user's query if not explicitly stated.")
    search_query: str | None = Field(default=None, description="The search query string. Required by filegen_qa_search. Use the user's query if not explicitly stated.")
    reasoning: str = Field(description="A brief explanation of why this tool was chosen and how arguments were determined.")


class AgentOrchestratorDecision(BaseModel):
    template_id: str | None = Field(default=None, description="The template ID (UUID). Required. Extract from the conversation context or user query.")
    company_data: str | None = Field(default=None, description="JSON string of company data for the orchestration. Required. Extract from the user query or conversation context.")
    reasoning: str = Field(description="A brief explanation of how the parameters were determined from the conversation.")

