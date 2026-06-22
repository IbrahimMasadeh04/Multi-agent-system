from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from src.features.agents.mcp_client import MCPClient  # type: ignore
from src.features.agents.schemas import FileGenRouterDecision  # type: ignore
from src.features.agents.state import AgentState  # type: ignore
from src.helper.shared import _message_text, _get_llm  # type: ignore


def _get_last_human_query(state: AgentState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return _message_text(m)
    return ""


def _get_filegen_context(state: AgentState) -> str:
    """Gather recent AI messages as accumulated context for the filegen sub-agents."""
    context_parts = []
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            context_parts.append(_message_text(m))
    context_parts.reverse()
    return "\n\n".join(context_parts) if context_parts else "No prior context."


client = MCPClient("http://127.0.0.1:8080/mcp")


##########################
#    FILEGEN ROUTER      #
##########################
async def filegen_router(state: AgentState):
    """
    Internal router for the file generation subgraph.
    Decides which file-gen sub-agent should handle the current task.
    """
    print("\n" + "="*20 + " [FILEGEN_ROUTER] " + "="*20)

    llm = _get_llm(TEMPERATURE=0.0).with_structured_output(
        FileGenRouterDecision, method="function_calling"
    )

    user_query = _get_last_human_query(state)
    context = _get_filegen_context(state)

    system_prompt = await client.get_prompt("file_gen router prompt")
    system_prompt = system_prompt.format(context=context, query=user_query)

    try:
        res = await llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  FileGen Router Decision: {res.next_node} | Reasoning: {res.reasoning}")
    except Exception as exc:
        print(f"  FileGen Router Error: {exc}. Falling back to 'done'.")
        return {"filegen_next": "done"}

    return {"filegen_next": res.next_node}


##########################
#   TEMPLATE MANAGER     #
##########################
async def template_manager_node(state: AgentState):
    """
    Handles template browsing, inspection, and upload operations.
    MCP Tools: filegen_list_templates, filegen_get_template, filegen_upload_template
    """
    print("\n" + "="*20 + " [TEMPLATE_MANAGER] " + "="*20)

    user_query = _get_last_human_query(state)
    context = _get_filegen_context(state)

    from src.features.agents.schemas import TemplateManagerDecision  # type: ignore

    decision_llm = _get_llm(TEMPERATURE=0.0).with_structured_output(
        TemplateManagerDecision, method="function_calling"
    )

    system_prompt = await client.get_prompt("template_manager prompt")
    system_prompt = system_prompt.format(query=user_query, context=context)

    try:
        decision = await decision_llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  Template Manager Decision: tool={decision.tool_name} | template_id={decision.template_id} | reasoning={decision.reasoning}")

        if decision.tool_name == "filegen_list_templates":
            print("  Calling: filegen_list_templates")
            result = await client.call_tool("filegen_list_templates", {})

        elif decision.tool_name == "filegen_get_template":
            if decision.template_id:
                print(f"  Calling: filegen_get_template({decision.template_id})")
                result = await client.call_tool("filegen_get_template", {"template_id": decision.template_id})
            else:
                print("  No template_id provided by LLM. Falling back to filegen_list_templates")
                result = await client.call_tool("filegen_list_templates", {})

        elif decision.tool_name == "filegen_upload_template":
            print("  Upload requested — needs user approval (not yet implemented)")
            result = "Template upload requires user approval. Please provide the file path, company ID, and template name."

        else:
            print("  Unexpected tool_name. Defaulting to filegen_list_templates")
            result = await client.call_tool("filegen_list_templates", {})


        print(f"  Template Manager Result: {str(result)[:200]}...")
        return {
            "messages": [AIMessage(content=f"[Template Manager Results]: {result}")]
        }

    except Exception as exc:
        print(f"  Template Manager Error: {exc}")
        return {
            "messages": [AIMessage(content=f"[Template Manager Error]: {exc}")]
        }


##########################
#   TEMPLATE FILLER      #
##########################
async def template_filler_node(state: AgentState):
    """
    Fills templates with company data using LLM + RAG.
    MCP Tools: filegen_fill_template, filegen_fill_preview, filegen_fill_history, filegen_get_version
    """
    print("\n" + "="*20 + " [TEMPLATE_FILLER] " + "="*20)

    user_query = _get_last_human_query(state)
    context = _get_filegen_context(state)

    from src.features.agents.schemas import TemplateFillerDecision  # type: ignore

    decision_llm = _get_llm(TEMPERATURE=0.0).with_structured_output(
        TemplateFillerDecision, method="function_calling"
    )

    system_prompt = await client.get_prompt("template_filler prompt")
    system_prompt = system_prompt.format(query=user_query, context=context)

    try:
        decision = await decision_llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  Template Filler Decision: tool={decision.tool_name} | template_id={decision.template_id} | reasoning={decision.reasoning}")

        if not decision.template_id:
            result = "Could not determine template_id. Please specify which template to use."

        elif decision.tool_name == "filegen_fill_history":
            print(f"  Calling: filegen_fill_history({decision.template_id})")
            result = await client.call_tool("filegen_fill_history", {"template_id": decision.template_id})

        elif decision.tool_name in ("filegen_fill_template", "filegen_fill_preview"):
            company_data = decision.company_data or "{}"
            print(f"  Calling: {decision.tool_name} with template_id={decision.template_id}")
            result = await client.call_tool(decision.tool_name, {
                "template_id": decision.template_id,
                "company_data": company_data,
            })

        elif decision.tool_name == "filegen_get_version":
            if decision.version_id:
                print(f"  Calling: filegen_get_version({decision.template_id}, {decision.version_id})")
                result = await client.call_tool("filegen_get_version", {
                    "template_id": decision.template_id,
                    "version_id": decision.version_id,
                })
            else:
                result = "Could not determine version_id. Please provide a version ID."

        else:
            result = f"Unexpected tool: {decision.tool_name}"

        print(f"  Template Filler Result: {str(result)[:200]}...")
        return {
            "messages": [AIMessage(content=f"[Template Filler Results]: {result}")]
        }

    except Exception as exc:
        print(f"  Template Filler Error: {exc}")
        return {
            "messages": [AIMessage(content=f"[Template Filler Error]: {exc}")]
        }


##########################
#     TEMPLATE QA        #
##########################
async def template_qa_node(state: AgentState):
    """
    Handles RAG-based Q&A about templates.
    MCP Tools: filegen_ask_question, filegen_qa_history, filegen_qa_search
    """
    print("\n" + "="*20 + " [TEMPLATE_QA] " + "="*20)

    user_query = _get_last_human_query(state)
    context = _get_filegen_context(state)

    from src.features.agents.schemas import TemplateQADecision  # type: ignore

    decision_llm = _get_llm(TEMPERATURE=0.0).with_structured_output(
        TemplateQADecision, method="function_calling"
    )

    system_prompt = await client.get_prompt("template_qa prompt")
    system_prompt = system_prompt.format(query=user_query, context=context)

    try:
        decision = await decision_llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  Template QA Decision: tool={decision.tool_name} | template_id={decision.template_id} | reasoning={decision.reasoning}")

        if not decision.template_id:
            result = "Could not determine template_id. Please specify which template you want to ask about."

        elif decision.tool_name == "filegen_qa_history":
            print(f"  Calling: filegen_qa_history({decision.template_id})")
            result = await client.call_tool("filegen_qa_history", {"template_id": decision.template_id})

        elif decision.tool_name == "filegen_qa_search":
            search_query = decision.search_query or user_query
            print(f"  Calling: filegen_qa_search({decision.template_id}, {search_query})")
            result = await client.call_tool("filegen_qa_search", {"template_id": decision.template_id, "query": search_query})

        elif decision.tool_name == "filegen_ask_question":
            question = decision.question or user_query
            print(f"  Calling: filegen_ask_question({decision.template_id}, {question})")
            result = await client.call_tool("filegen_ask_question", {"template_id": decision.template_id, "question": question})

        else:
            result = f"Unexpected tool: {decision.tool_name}"

        print(f"  Template QA Result: {str(result)[:200]}...")
        return {
            "messages": [AIMessage(content=f"[Template QA Results]: {result}")]
        }

    except Exception as exc:
        print(f"  Template QA Error: {exc}")
        return {
            "messages": [AIMessage(content=f"[Template QA Error]: {exc}")]
        }


##########################
#  TEMPLATE GENERATOR    #
##########################
# async def template_generator_node(state: AgentState):
#     """
#     Generates new templates from scratch using LLM.
#     MCP Tools: filegen_generate_template, filegen_get_generation_types
#     """
#     print("\n" + "="*20 + " [TEMPLATE_GENERATOR] " + "="*20)

#     user_query = _get_last_human_query(state)
#     context = _get_filegen_context(state)

#     llm = _get_llm(TEMPERATURE=0.0)

#     system_prompt = await client.get_prompt("template_generator prompt")
#     system_prompt = system_prompt.format(query=user_query, context=context)

#     try:
#         response = await llm.ainvoke([SystemMessage(content=system_prompt)])
#         decision = _message_text(response).strip()
#         print(f"  Template Generator LLM Response: {decision[:200]}...")

#         import json
#         import re
#         lower_decision = decision.lower()

#         if "get_generation_types" in lower_decision or "types" in lower_decision and "list" in lower_decision:
#             print("  Calling: filegen_get_generation_types")
#             result = await client.call_tool("filegen_get_generation_types", {})

#         else:
#             # Extract generation parameters from the LLM response
#             name_match = re.search(r'template_name["\s:=]+["\']([^"\']+)["\']', decision)
#             type_match = re.search(r'template_type["\s:=]+["\']([^"\']+)["\']', decision)
#             company_match = re.search(r'company_type["\s:=]+["\']([^"\']+)["\']', decision)
#             sections_match = re.search(r'num_sections["\s:=]+["\']?(\d+)', decision)
#             context_match = re.search(r'additional_context["\s:=]+["\']([^"\']+)["\']', decision)

#             template_name = name_match.group(1) if name_match else None
#             template_type = type_match.group(1) if type_match else None
#             company_type = company_match.group(1) if company_match else None

#             if not all([template_name, template_type, company_type]):
#                 result = (
#                     "I need more details to generate a template. Please provide:\n"
#                     "- Template name (e.g., 'Sales Proposal')\n"
#                     "- Template type (e.g., proposal, report, contract, invoice)\n"
#                     "- Company/industry type (e.g., SaaS, Manufacturing, Finance)\n"
#                     "- Optionally: number of sections and additional context"
#                 )
#                 print(f"  Missing parameters. Asking user for details.")
#             else:
#                 args = {
#                     "template_name": template_name,
#                     "template_type": template_type,
#                     "company_type": company_type,
#                     "num_sections": sections_match.group(1) if sections_match else "5",
#                 }
#                 if context_match:
#                     args["additional_context"] = context_match.group(1)

#                 print(f"  Calling: filegen_generate_template({template_name}, {template_type}, {company_type})")
#                 result = await client.call_tool("filegen_generate_template", args)

#         print(f"  Template Generator Result: {str(result)[:200]}...")
#         return {
#             "messages": [AIMessage(content=f"[Template Generator Results]: {result}")]
#         }

#     except Exception as exc:
#         print(f"  Template Generator Error: {exc}")
#         return {
#             "messages": [AIMessage(content=f"[Template Generator Error]: {exc}")]
#         }


##########################
#  AGENT ORCHESTRATOR    #
##########################
async def agent_orchestrator_node(state: AgentState):
    """
    Runs the full automated workflow: fill + validate + QA in one call.
    MCP Tools: filegen_agent_orchestrate
    """
    print("\n" + "="*20 + " [AGENT_ORCHESTRATOR] " + "="*20)

    user_query = _get_last_human_query(state)
    context = _get_filegen_context(state)

    from src.features.agents.schemas import AgentOrchestratorDecision  # type: ignore

    decision_llm = _get_llm(TEMPERATURE=0.0).with_structured_output(
        AgentOrchestratorDecision, method="function_calling"
    )

    system_prompt = await client.get_prompt("agent_orchestrator prompt")
    system_prompt = system_prompt.format(query=user_query, context=context)

    try:
        decision = await decision_llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  Agent Orchestrator Decision: template_id={decision.template_id} | reasoning={decision.reasoning}")

        if decision.template_id and decision.company_data:
            print(f"  Calling: filegen_agent_orchestrate({decision.template_id})")
            result = await client.call_tool("filegen_agent_orchestrate", {
                "template_id": decision.template_id,
                "company_data": decision.company_data,
            })
        else:
            missing = []
            if not decision.template_id:
                missing.append("template_id")
            if not decision.company_data:
                missing.append("company_data (as JSON)")
            result = f"Missing required parameters: {', '.join(missing)}. Please provide them to run the full orchestration."

        print(f"  Agent Orchestrator Result: {str(result)[:200]}...")
        return {
            "messages": [AIMessage(content=f"[Agent Orchestrator Results]: {result}")]
        }

    except Exception as exc:
        print(f"  Agent Orchestrator Error: {exc}")
        return {
            "messages": [AIMessage(content=f"[Agent Orchestrator Error]: {exc}")]
        }
