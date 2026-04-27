from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from sqlalchemy import inspect

from src.features.agents.system_prompts import (
    DB_ANALYST_PROMPT, 
    INTENT_ANALYZER_PROMPT, 
    PLANNER_PROMPT, 
    SYNTHESIZER_PROMPT,
    ORCHESTRATOR_PROMPT
)
from src.features.agents.schemas import ComplexityDecision, IntentSchema, PlannerOutput, RouterDecision
from src.features.db_analyst.tools import execute_sql_query
from src.features.agents.state import AgentState
from src.features.ingestion.service import search_internal_docs_with_score
from src.helper.config import get_settings
from src.helper.shared import _message_text, _get_llm, _get_db


def _get_last_human_query(state: AgentState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return _message_text(m)
    return ""


##########################
#    INTENT ANALYZER     #
##########################
async def intent_analyzer(state: AgentState):
    """
    Analyzes the user's intent to decide which worker to route to.
    """
    print("\n" + "="*20 + " [INTENT_ANALYZER] " + "="*20)
    
    if state.get("messages") and isinstance(state["messages"][-1], AIMessage):
         print("  Detected AI Message as latest. Routing directly to Synthesizer.")
         return {"next_node": "synthesizer"}

    llm = _get_llm(TEMPERATURE=0.0).with_structured_output(IntentSchema, method="function_calling")
    last_message = _get_last_human_query(state)
    
    print(f"  Raw User Input: '{last_message}'")
    
    # Use the messages from the checkpointer (state) to build the history
    history_str = "\n".join([f"{'User: ' if isinstance(m, HumanMessage) else 'AI: '}{_message_text(m)}" for m in state.get("messages", [])[:-1]])

    system_prompt = INTENT_ANALYZER_PROMPT

    messages = [
        SystemMessage(content=system_prompt.format(history=history_str, query=last_message))
    ]
    
    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        print(f"  Intent Analysis Error: {exc}")
        return {"next_node": "synthesizer"}
    
    print(f"  Primary Intent: {response.primary_intent}")
    print(f"  Domain: {response.domain}")
    print(f"  Confidence: {response.confidence}")
    print(f"  Entities: {response.entities}")

    # Store schema directly as a dict for TypedDict state compatibility
    return {"intent_data": response.model_dump()}

##########################
#        PLANNER         #
##########################


async def planner_node(state: AgentState):
    print("\n" + "="*20 + " [PLANNER] " + "="*20)
    print("  Creating Step-by-Step Plan...")
    
    llm = _get_llm(TEMPERATURE=0.0).with_structured_output(PlannerOutput, method="function_calling")
    last_message = _get_last_human_query(state)
    
    system_prompt = PLANNER_PROMPT
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=last_message)]
    
    try:
        response = await llm.ainvoke(messages)
        plan = response.tasks
    except Exception as exc:
        print(f"  Planner Error: {exc}")
        plan = []
    
    print(f"  Generated plan: {plan}")
    return {"plan": plan, "past_steps": []}

##########################
#      ORCHESTRATOR      #
##########################
async def orchestrator(state: AgentState):
    """
    Orchestrator acts as a Router based on LLM decision-making.
    """
    print("\n" + "="*20 + " [ORCHESTRATOR] " + "="*20)
    
    intent_data = state.get("intent_data", {})
    plan = state.get("plan") or []
    past_steps = state.get("past_steps") or []
    
    last_message = _get_last_human_query(state)

    llm = _get_llm(TEMPERATURE=0.0).with_structured_output(RouterDecision, method="function_calling")

    system_prompt = ORCHESTRATOR_PROMPT.format(
        intent_data=intent_data,
        plan=plan,
        past_steps=past_steps,
        query=last_message
    )

    try:
        res = await llm.ainvoke([SystemMessage(content=system_prompt)])
        print(f"  AI Router Decision: {res.next_node} | Reasoning: {res.reasoning}")
    except Exception as exc:
        print(f"  Router LLM Error: {exc}. Falling back to synthesizer.")
        return {"next_node": "synthesizer"}

    next_node = res.next_node
    
    # State update logic
    state_updates = {"next_node": next_node}
    
    if len(plan) > 0 and next_node not in ["planner", "synthesizer"]:
        current_task = plan[0]
        updated_plan = plan[1:]
        updated_past_steps = past_steps + [current_task]
        
        print(f"  Consuming plan task: '{current_task}'")
        state_updates.update({
            "plan": updated_plan,
            "current_task": current_task,
            "past_steps": updated_past_steps
        })
    elif next_node not in ["planner", "synthesizer"] and len(past_steps) == 0:
        # direct execution
        state_updates.update({
            "past_steps": ["direct_execution"]
        })

    return state_updates


#############################
#      INTERNAL WORKER      #
#############################
async def internal_worker(state: AgentState):
    """
    Subagent for internal PDF/vector knowledge search.
    """
    print("\n" + "="*20 + " [INTERNAL_SEARCH] " + "="*20)
    print("  Task: Searching Internal Documents / PDF Knowledge Base")
    
    user_query = _get_last_human_query(state)
    try:
        combined_text, best_score = await search_internal_docs_with_score(user_query)
        print(f"  Search Score: {best_score}")
        return {
            "messages": [AIMessage(content=f"Internal Search Results (Score: {best_score}): {combined_text}")],
            "search_score": best_score
        }
    except Exception as exc:
        print(f"  Search Error: {exc}")
        return {
            "messages": [AIMessage(content=f"Internal Search Results: (Error) {exc}")],
            "search_score": 0.0
        }



############################
#      EXTERNAL WORKER     #
############################
async def external_worker(state: AgentState):
    """
    Subagent for external web search.
    """
    print("\n" + "="*20 + " [EXTERNAL_SEARCH] " + "="*20)
    print("  Task: Searching External Web via Tavily")
    
    user_query = _get_last_human_query(state)
    settings = get_settings()
    if not settings.TAVILY_API_KEY:
        print("  Error: TAVILY_API_KEY is missing.")
        return {
            "messages": [AIMessage(content="External Search Results: TAVILY_API_KEY missing.")]
        }

    try:
        search = TavilySearch(max_results=2, tavily_api_key=settings.TAVILY_API_KEY)
        results = await search.ainvoke(user_query)
        print(f"  Search completed successfully.")
        return {
            "messages": [AIMessage(content=f"External Search Results: {results}")]
        }
    except Exception as exc:
        print(f"  External Search Error: {exc}")
        return {
            "messages": [AIMessage(content=f"External Search Results: (Error) {exc}")]
        }


##########################
#      DB WORKER         #
##########################
async def db_analyst_worker(state: AgentState):

    try:
        print("\n" + "="*20 + " [DB_ANALYST] " + "="*20)
        print("  Task: Querying Database and execution")
        
        query = _get_last_human_query(state)
        print(f"  DEBUG: DB Analyst received query: {query}\n")

        tools = [execute_sql_query]
        llm_with_tools = _get_llm(TEMPERATURE=0.0).bind_tools(tools)

        system_prompt = DB_ANALYST_PROMPT

        # Get the tables info from SQLAlchemy inspector
        inspector = inspect(_get_db()._engine)
        table_names = inspector.get_table_names()
        tables = ", ".join(table_names) if table_names else "No tables found."

        schema = ""
        if table_names:
            for table_name in table_names:
                columns = inspector.get_columns(table_name)
                schema += f"Table: {table_name}\n"
                for col in columns:
                    schema += f" - {col['name']} ({col['type']})\n"
                schema += "\n"
        schemas = schema if schema else "No schema information available."

        print(f"  DEBUG: DB Tables: {tables}\n")
        
        # Give context of the last few turns (system + conversation history)
        conversation_context = [SystemMessage(content=system_prompt.format(sql_tables=tables, sql_schemas=schemas))]
        
        # Grab up to the last 5 messages from the history to provide to the DB Analyst LLM
        for msg in state.get("messages", [])[-5:]:
            conversation_context.append(msg)

        response = await llm_with_tools.ainvoke(conversation_context)

        # Check if model called a tool
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call['name'] == 'execute_sql_query':
                    sql_query = tool_call['args'].get('query', '')
                    print(f"  Generated SQL Query: {sql_query}")
                    
                    is_write = any(kw in sql_query.upper() for kw in ["UPDATE", "INSERT", "DELETE", "DROP", "ALTER"])
                    intent_data = state.get("intent_data") or {}
                    primary_intent = intent_data.get("primary_intent", "")

                    if is_write or primary_intent == "UPDATE_DATA" or intent_data.get("requires_confirmation"):
                        print(f"  Graph Interrupted. Awaiting Approval for Query: {sql_query}")
                        # Return pending SQL to pause before sql_executor_node
                        return {
                            "pending_sql": sql_query,
                            "requires_confirmation": True,
                            "messages": [AIMessage(content=f"[SYSTEM] Write operation detected and paused for approval:\n\n```sql\n{sql_query}\n```")]
                        }
                    else:
                        tool_result = execute_sql_query.invoke(tool_call['args'])
                        
                        # Summarize the result instead of just returning raw string
                        summary_prompt = "Summarize the following SQL results for the user: {results}"
                        summary_res = await _get_llm().ainvoke([
                            SystemMessage(content="You are a helpful assistant."),
                            HumanMessage(content=summary_prompt.format(results=tool_result))
                        ])
                        return {
                            "messages": [AIMessage(content=summary_res.content)]
                        }
        else:
            # If LLM didn't call tool, check if intent_data indicates an UPDATE_DATA intent
            intent_data = state.get("intent_data") or {}
            
            if intent_data.get("primary_intent") == "UPDATE_DATA" or intent_data.get("requires_confirmation"):
                print(f"  Detected write intent from intent_data but tool not called. Reprompting LLM.")
                
                # Force fallback to generate SQL for write operation
                fallback_llm = _get_llm(TEMPERATURE=0.0).bind_tools(tools, tool_choice="execute_sql_query")
                fallback_msg = HumanMessage(content="You must use the execute_sql_query tool to generate the precise SQL for this update/insert/delete operation based on the schema.")
                
                fallback_res = await fallback_llm.ainvoke(conversation_context + [response, fallback_msg])
                
                if fallback_res.tool_calls:
                    for tool_call in fallback_res.tool_calls:
                        if tool_call['name'] == 'execute_sql_query':
                            sql_query = tool_call['args'].get('query', '')
                            print(f"  Generated SQL Query (Fallback): {sql_query}")
                            return {
                                "pending_sql": sql_query,
                                "requires_confirmation": True,
                                "messages": [AIMessage(content=f"[SYSTEM] Write operation detected and paused for approval:\n\n```sql\n{sql_query}\n```")]
                            }
                
                # If still failing to generate SQL
                return {
                    "pending_sql": f"-- Operation: {query}",
                    "requires_confirmation": True,
                    "messages": [AIMessage(content="[SYSTEM] Write operation detected but could not generate precise SQL. Please provide more details.")]
                }

        # Only return explanatory text if it's NOT a write operation
        if not response.content or response.content.strip() == "":
            print("  DB Analyst failed to answer the request.")
            return {
                "messages": [AIMessage(content="I couldn't find a way to answer that using the database.")]
            }

        return {
            "messages": [AIMessage(content=response.content)]
        }

    except Exception as exc:
        print(f"  DB Analyst Error: {exc}\n\n")
        return {
            "messages": [AIMessage(content=f"DB Analyst Results: (Error) {exc}")]
        }

##########################
#      SQL EXECUTOR      #
##########################
async def sql_executor_node(state: AgentState):
    """
    Executes pending SQL queries after user approval. (Phase B)
    """
    print("\n" + "="*20 + " [SQL_EXECUTOR] " + "="*20)
    
    pending_sql = state.get("pending_sql")
    user_approval = state.get("user_approval")
    
    if not pending_sql:
        print("  Error: No pending SQL query to execute.")
        return {"messages": [AIMessage(content="I don't have any pending database updates to execute.")], "requires_confirmation": False, "user_approval": None}
        
    if user_approval is True:
        print(f"  Graph Resumed. Executing Query: {pending_sql}")
        try:
            tool_result = execute_sql_query.invoke({"query": pending_sql})
            
            # Reset states and summarize
            return {
                "messages": [AIMessage(content=f"Successfully executed the targeted database modification! System returned: {tool_result}")],
                "pending_sql": None,
                "requires_confirmation": False,
                "user_approval": None
            }
        except Exception as exc:
            return {
                "messages": [AIMessage(content=f"Execution Failed: {exc}")],
                "pending_sql": None,
                "requires_confirmation": False,
                "user_approval": None
            }
    else:
        print("  User rejected the SQL query. Cancelling execution.")
        return {
            "messages": [AIMessage(content="The database operation was cancelled.")],
            "pending_sql": None,
            "requires_confirmation": False,
            "user_approval": None
        }

##########################
#      SYNTHESIZER       #
##########################
async def synthesizer(state: AgentState):
    """
    Takes all inputs and produces a logical, refined response.
    """
    print("\n" + "="*20 + " [SYNTHESIZER] " + "="*20)
    
    llm = _get_llm()
    
    current_turn_context = []
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            current_turn_context.append(_message_text(m))
    
    current_turn_context.reverse()
    context = "\n\n".join(current_turn_context)
    
    print(f"  Context length to synthesize: {len(context)} characters")
    
    system_prompt = SYNTHESIZER_PROMPT
    
    history = []
    last_human_idx = -1
    for i in range(len(state["messages"])-1, -1, -1):
        if isinstance(state["messages"][i], HumanMessage):
            last_human_idx = i
            break
            
    if last_human_idx != -1:
        history = list(state["messages"][:last_human_idx+1])
    else:
        history = list(state["messages"])
        
    if context and history and isinstance(history[-1], HumanMessage):
        last_human_msg = history[-1]
        augmented_text = f"{_message_text(last_human_msg)}\n\n[Subagent Context gathered for this query]:\n{context}"
        history[-1] = HumanMessage(content=augmented_text)
    
    messages = [SystemMessage(content=system_prompt)] + history
    
    final_response = await llm.ainvoke(messages)
    
    print(f"  Final Answer: '{final_response.content}'")
    
    return {"messages": [final_response]}
