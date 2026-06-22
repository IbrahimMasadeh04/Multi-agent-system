"""File Generation Service Tools — Full API Surface.

Exposes all endpoints of the File Generation Service as MCP tools.
Tools hit the FastAPI backend via httpx and follow the FastMCP
@mcp.tool() registration pattern used in src/tools/.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from src.helper.config import get_settings  # type: ignore

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BASE_URL: str = getattr(settings, "FILE_GENERATION_BASE_URL", "")


def _get_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an async HTTP client for the File Generation Service."""
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


def _fmt(data: Any) -> str:
    """Return a compact JSON string of *data*."""
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_file_generation_tools(mcp: FastMCP[Any]):
    """Register File Generation Service tools on the given MCP server."""

    # ======================================================================
    # 1. HEALTH
    # ======================================================================

    @mcp.tool()
    async def filegen_health_check() -> str:
        """
        Check the health status of the File Generation Service.
        Returns the current service status, uptime, and component health.
        """
        try:
            async with _get_client() as client:
                response = await client.get("/api/v1/health")
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_service_info() -> str:
        """
        Get detailed information about the File Generation Service.
        Returns service version, capabilities, and configuration details.
        """
        try:
            async with _get_client() as client:
                response = await client.get("/api/v1/info")
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ======================================================================
    # 2. TEMPLATES
    # ======================================================================

    @mcp.tool()
    async def filegen_upload_template(
        file_path: str,
        company_id: str,
        template_name: str,
    ) -> str:
        """
        Upload a new document template (PDF or DOCX) to the service.
        The file is read from the local filesystem and sent as multipart form data.
        After upload, the system extracts sections, chunks the document, and
        indexes it in Qdrant for vector search.

        PARAMETERS:
          file_path      – Absolute path to a PDF or DOCX file on disk.
          company_id     – The company ID to associate this template with.
          template_name  – A human-readable name for the template.
        """
        try:
            if not os.path.isfile(file_path):
                raise Exception(f"File not found: {file_path}")

            filename = os.path.basename(file_path)
            # Determine content type
            ext = os.path.splitext(filename)[1].lower()
            content_types = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }
            content_type = content_types.get(ext, "application/octet-stream")

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            async with httpx.AsyncClient(base_url=_BASE_URL, timeout=60.0) as client:
                response = await client.post(
                    "/api/v1/templates/upload",
                    files={"file": (filename, file_bytes, content_type)},
                    data={
                        "company_id": company_id,
                        "template_name": template_name,
                    },
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_list_templates() -> str:
        """
        List all templates stored in the File Generation Service.
        Returns template metadata including IDs, names, types, and section counts.
        """
        try:
            async with _get_client() as client:
                response = await client.get("/api/v1/templates/list")
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_get_template(template_id: str) -> str:
        """
        Get detailed information about a specific template.
        Returns template metadata, sections, placeholders, and version history.

        PARAMETERS:
          template_id – The unique ID of the template.
        """
        try:
            async with _get_client() as client:
                response = await client.get(f"/api/v1/templates/{template_id}")
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    # @mcp.tool()
    # async def filegen_delete_template(template_id: str) -> str:
    #     """
    #     Delete a template and all its associated data (versions, Q&A records,
    #     vector embeddings) from the File Generation Service.

    #     PARAMETERS:
    #       template_id – The unique ID of the template to delete.
    #     """
    #     try:
    #         async with _get_client() as client:
    #             response = await client.delete(f"/api/v1/templates/{template_id}")
    #             response.raise_for_status()
    #             return _fmt(response.json())
    #     except httpx.HTTPStatusError as e:
    #         raise Exception(f"HTTP {e.response.status_code}: {e}")
    #     except httpx.TimeoutException:
    #         raise Exception("Request timed out")
    #     except httpx.ConnectError:
    #         raise Exception("Could not connect to File Generation Service")
    #     except Exception as e:
    #         raise Exception(str(e))

    # ======================================================================
    # 3. FILL
    # ======================================================================

    @mcp.tool()
    async def filegen_fill_template(
        template_id: str,
        company_data: str,
        additional_context: Optional[str] = None,
        temperature: Optional[str] = None,
    ) -> str:
        """
        Fill a template with company data using LLM + RAG context.
        The system retrieves relevant context from Qdrant, generates content
        for each section using the LLM, and saves the filled version.

        PARAMETERS:
          template_id        – The unique ID of the template to fill.
          company_data       – JSON string of company data to fill placeholders with.
                               Example: '{"company_name": "Acme Corp", "industry": "SaaS"}'
          additional_context – Optional extra instructions for the LLM.
          temperature        – Optional LLM temperature (e.g. "0.7"). Controls creativity.
        """
        try:
            body: dict[str, Any] = {
                "company_data": json.loads(company_data),
            }
            if additional_context:
                body["additional_context"] = additional_context
            if temperature:
                body["temperature"] = float(temperature)

            async with _get_client(timeout=120.0) as client:
                response = await client.post(
                    f"/api/v1/templates/{template_id}/fill",
                    json=body,
                )
                response.raise_for_status()
                return _fmt(response.json())
        except json.JSONDecodeError:
            raise Exception("company_data must be a valid JSON string")
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out (template fill can take up to 2 minutes)")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_fill_preview(
        template_id: str,
        company_data: str,
        additional_context: Optional[str] = None,
        temperature: Optional[str] = None,
    ) -> str:
        """
        Preview a filled template WITHOUT saving it.
        Useful for reviewing the generated content before committing.

        PARAMETERS:
          template_id        – The unique ID of the template to preview.
          company_data       – JSON string of company data to fill placeholders with.
          additional_context – Optional extra instructions for the LLM.
          temperature        – Optional LLM temperature (e.g. "0.7").
        """
        try:
            body: dict[str, Any] = {
                "company_data": json.loads(company_data),
            }
            if additional_context:
                body["additional_context"] = additional_context
            if temperature:
                body["temperature"] = float(temperature)

            async with _get_client(timeout=120.0) as client:
                response = await client.post(
                    f"/api/v1/templates/{template_id}/fill-preview",
                    json=body,
                )
                response.raise_for_status()
                return _fmt(response.json())
        except json.JSONDecodeError:
            raise Exception("company_data must be a valid JSON string")
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_fill_history(template_id: str) -> str:
        """
        Get the fill version history for a template.
        Returns all previous fill versions with timestamps and metadata.

        PARAMETERS:
          template_id – The unique ID of the template.
        """
        try:
            async with _get_client() as client:
                response = await client.get(
                    f"/api/v1/templates/{template_id}/fill-history"
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_get_version(template_id: str, version_id: str) -> str:
        """
        Get a specific filled version of a template.
        Returns the full filled content for that version.

        PARAMETERS:
          template_id – The unique ID of the template.
          version_id  – The unique ID of the fill version.
        """
        try:
            async with _get_client() as client:
                response = await client.get(
                    f"/api/v1/templates/{template_id}/versions/{version_id}"
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    # @mcp.tool()
    # async def filegen_delete_version(template_id: str, version_id: str) -> str:
    #     """
    #     Delete a specific filled version of a template.

    #     PARAMETERS:
    #       template_id – The unique ID of the template.
    #       version_id  – The unique ID of the fill version to delete.
    #     """
    #     try:
    #         async with _get_client() as client:
    #             response = await client.delete(
    #                 f"/api/v1/templates/{template_id}/versions/{version_id}"
    #             )
    #             response.raise_for_status()
    #             return _fmt(response.json())
    #     except httpx.HTTPStatusError as e:
    #         raise Exception(f"HTTP {e.response.status_code}: {e}")
    #     except httpx.TimeoutException:
    #         raise Exception("Request timed out")
    #     except httpx.ConnectError:
    #         raise Exception("Could not connect to File Generation Service")
    #     except Exception as e:
    #         raise Exception(str(e))

    # ======================================================================
    # 4. Q&A (RAG-based)
    # ======================================================================

    @mcp.tool()
    async def filegen_ask_question(template_id: str, question: str) -> str:
        """
        Ask a question about a template using RAG-based Q&A.
        The system searches Qdrant for relevant sections, then uses the LLM
        to generate an answer with a confidence score.

        PARAMETERS:
          template_id – The unique ID of the template to ask about.
          question    – The question to ask about the template content.
        """
        try:
            async with _get_client(timeout=60.0) as client:
                response = await client.post(
                    f"/api/v1/templates/{template_id}/ask",
                    json={"question": question},
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_qa_history(template_id: str) -> str:
        """
        Get the Q&A history for a template.
        Returns all previous questions, answers, and confidence scores.

        PARAMETERS:
          template_id – The unique ID of the template.
        """
        try:
            async with _get_client() as client:
                response = await client.get(
                    f"/api/v1/templates/{template_id}/qa-history"
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_qa_search(template_id: str, query: str) -> str:
        """
        Search through Q&A history for a template using semantic search.
        Finds previously asked questions and answers matching the query.

        PARAMETERS:
          template_id – The unique ID of the template.
          query       – The search query to find relevant Q&A entries.
        """
        try:
            async with _get_client() as client:
                response = await client.post(
                    f"/api/v1/templates/{template_id}/qa-search",
                    json={"query": query},
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    # @mcp.tool()
    # async def filegen_delete_qa(template_id: str, qa_id: str) -> str:
    #     """
    #     Delete a specific Q&A entry from a template's history.

    #     PARAMETERS:
    #       template_id – The unique ID of the template.
    #       qa_id       – The unique ID of the Q&A entry to delete.
    #     """
    #     try:
    #         async with _get_client() as client:
    #             response = await client.delete(
    #                 f"/api/v1/templates/{template_id}/qa-history/{qa_id}"
    #             )
    #             response.raise_for_status()
    #             return _fmt(response.json())
    #     except httpx.HTTPStatusError as e:
    #         raise Exception(f"HTTP {e.response.status_code}: {e}")
    #     except httpx.TimeoutException:
    #         raise Exception("Request timed out")
    #     except httpx.ConnectError:
    #         raise Exception("Could not connect to File Generation Service")
    #     except Exception as e:
    #         raise Exception(str(e))

    # ======================================================================
    # 5. AGENT ORCHESTRATION
    # ======================================================================

    @mcp.tool()
    async def filegen_agent_orchestrate(
        template_id: str,
        company_data: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        Run the full agent-orchestrated workflow: fill template + validate + Q&A.
        This is a single-call endpoint that uses OpenAI GPT-4o with function
        calling to intelligently orchestrate the entire process:
          1. Fills the template with company data using LLM + RAG
          2. Validates quality (completeness, relevance, grammar, consistency, accuracy)
          3. Asks 7-10 strategic QA questions and verifies answers
          4. Retrieves and verifies vector context
          5. Makes a final recommendation (APPROVED, NEEDS_REVISION, MANUAL_REVIEW, etc.)

        NOTE: This operation typically takes 20-45 seconds.

        PARAMETERS:
          template_id        – The unique ID of the template to process.
          company_data       – JSON string of company data to fill placeholders with.
                               Example: '{"company_name": "Acme Corp", "industry": "SaaS"}'
          additional_context – Optional extra instructions for the agent.
        """
        try:
            body: dict[str, Any] = {
                "company_data": json.loads(company_data),
            }
            if additional_context:
                body["additional_context"] = additional_context

            async with _get_client(timeout=120.0) as client:
                response = await client.post(
                    f"/api/v1/agent/{template_id}/orchestrate-fill-and-qa",
                    json=body,
                )
                response.raise_for_status()
                return _fmt(response.json())
        except json.JSONDecodeError:
            raise Exception("company_data must be a valid JSON string")
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception(
                "Request timed out — agent orchestration can take up to 2 minutes"
            )
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ======================================================================
    # 6. TEMPLATE GENERATION
    # ======================================================================

    @mcp.tool()
    async def filegen_generate_template(
        template_name: str,
        template_type: str,
        company_type: str,
        num_sections: str = "5",
        additional_context: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a brand-new template from scratch using LLM.
        Creates a professional document template with sections, placeholders,
        and saves it to both PostgreSQL and Qdrant. The generated template
        is immediately ready to use.

        PARAMETERS:
          template_name      – Name for the template (e.g. "Sales Proposal").
          template_type      – Type of template. Supported types include:
                               proposal, report, contract, invoice, letter,
                               memo, plan, policy, procedure, manual,
                               specification, agreement, statement, brief.
          company_type       – Industry type. Supported types include:
                               SaaS, Manufacturing, Finance, Healthcare,
                               Retail, Education, Technology, Consulting,
                               RealEstate, Legal, Marketing, Logistics,
                               Energy, Hospitality.
          num_sections       – Number of sections to generate (default "5").
          additional_context – Optional extra instructions for template generation.
        """
        try:
            body: dict[str, Any] = {
                "template_name": template_name,
                "template_type": template_type,
                "company_type": company_type,
                "num_sections": int(num_sections),
                "temperature": float(temperature),
            }
            if additional_context:
                body["additional_context"] = additional_context

            async with _get_client(timeout=90.0) as client:
                response = await client.post(
                    "/api/v1/templates/generate",
                    json=body,
                )
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out — template generation can take up to 90 seconds")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))

    # ------------------------------------------------------------------

    @mcp.tool()
    async def filegen_get_generation_types() -> str:
        """
        Get all supported template types and company/industry types
        for template generation. Use this to discover valid values
        for the filegen_generate_template tool.
        """
        try:
            async with _get_client() as client:
                response = await client.get("/api/v1/templates/generation-types")
                response.raise_for_status()
                return _fmt(response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e}")
        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.ConnectError:
            raise Exception("Could not connect to File Generation Service")
        except Exception as e:
            raise Exception(str(e))