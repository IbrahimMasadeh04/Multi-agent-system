from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from sqlalchemy import inspect

from src.features.agents.schemas import ComplexityDecision, IntentSchema, PlannerOutput
from src.features.db_analyst.tools import execute_sql_query
from src.features.agents.state import AgentState
from src.features.ingestion.service import search_internal_docs_with_score
from src.helper.config import get_settings
from src.helper.shared import _message_text, _get_llm, db


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

    system_prompt = """You are an expert intent analyzer and entity extractor.
    Your task is to analyze the user's LATEST query and extract structured intent, entities, domain, and confidence.
    
    IMPORTANT: Use the Conversation History ONLY as a reference to resolve pronouns or contextual references (e.g., "it", "them", "both") in the Latest Query. Do NOT evaluate the intent of past queries, only the Latest Query.
    
    Conversation History:
    {history}

    Few-shot examples:
    User: "Hi there!" -> primary_intent: GREETING, domain: WEB, confidence: 1.0, requires_confirmation: False, entities: []
    User: "How many laptops do we have in inventory?" -> primary_intent: QUERY_DATA, domain: DB, confidence: 0.95, requires_confirmation: False, entities: [{{"item_name": "laptop"}}]
    User: "What are the cost price for them?" (where history discusses laptops) -> primary_intent: QUERY_DATA, domain: DB, confidence: 0.95, requires_confirmation: False, entities: [{{"item_name": "laptop", "attribute": "cost price"}}]
    User: "Update its price to $500" (where 'its' refers to a monitor in history) -> primary_intent: UPDATE_DATA, domain: DB, confidence: 0.9, requires_confirmation: True, entities: [{{"item_name": "monitor", "price": 500}}]
    User: "What does the employee handbook say about PTO?" -> primary_intent: QUERY_DATA, domain: PDF_DOCS, confidence: 0.9, requires_confirmation: False, entities: [{{"topic": "PTO"}}]
    
    Latest Query: {query}"""

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
    
    system_prompt = """You are an AI planner. Break down the user's query into a step-by-step plan.
    Use the available workers:
    - db_analyst (database SQL queries)
    - internal_search (internal PDF docs)
    - external_search (web search)
    Return a JSON list of strings (tasks) indicating the exact steps to accomplish the user's request.
    Example Format: ["Search prices in DB", "Search market prices on Web", "Compare results"]"""
    
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
    Orchestrator acts as a Router based on the structured JSON provided by intent_analyzer or current plan.
    """
    print("\n" + "="*20 + " [ORCHESTRATOR] " + "="*20)
    
    intent_data = state.get("intent_data")
    if not intent_data:
        print("  Final Decision: synthesizer (Fallback due to missing intent_data)")
        return {"next_node": "synthesizer"}
        
    primary_intent = intent_data.get("primary_intent")
    domain = intent_data.get("domain")
    
    plan = state.get("plan") or []
    past_steps = state.get("past_steps")
    
    # 1. If state['plan'] is NOT empty
    if len(plan) > 0:
        current_task = plan[0]
        remaining_plan = plan[1:]
        safe_past_steps = past_steps or []
        
        print(f"  Printing current plan: {plan}")
        print(f"  Executing step {len(safe_past_steps) + 1} of {len(safe_past_steps) + len(plan)}: {current_task}")
        
        task_lower = current_task.lower()
        if "db" in task_lower or "database" in task_lower or "sql" in task_lower:
            next_node = "db_analyst"
        elif "internal" in task_lower or "pdf" in task_lower or "web" in task_lower or "external" in task_lower or "market" in task_lower or "search" in task_lower:
            next_node = "internal_search"
        else:
            next_node = "db_analyst" if domain == "DB" else "internal_search"
            
        print(f"  Routing mapped task to: {next_node}")
        
        updated_past_steps = safe_past_steps + [current_task]
        return {"plan": remaining_plan, "current_task": current_task, "past_steps": updated_past_steps, "next_node": next_node}
    
    # 2. Planning logic
    last_message = _get_last_human_query(state)

    try:
        complexity_llm = _get_llm(TEMPERATURE=0.0).with_structured_output(ComplexityDecision, method="function_calling")
        complexity_res = await complexity_llm.ainvoke([
            SystemMessage(content="Determine if the user query is complex (requires a multi-step plan, comparisons, or gathering data from multiple sources)."),
            HumanMessage(content=last_message)
        ])
        is_complex = complexity_res.is_complex
        print(f"  LLM evaluated query complexity: {is_complex}")
    except Exception as exc:
        print(f"  LLM complexity check failed: {exc}")
        is_complex = len(intent_data.get("entities", [])) > 1

    if past_steps is None:
        if is_complex:
            print("  Complex intent detected. Routing to: planner")
            return {"next_node": "planner"}
        else:
            if primary_intent == "GREETING":
                next_node = "synthesizer"
            elif domain == "DB":
                next_node = "db_analyst"
            elif domain in ["PDF_DOCS", "WEB"] or primary_intent in ["QUERY_DATA", "UPDATE_DATA"]:
                # Always hit internal search first for any search request
                next_node = "internal_search" if domain != "DB" else "db_analyst"
            else:
                next_node = "synthesizer"
                
            print(f"  Simple intent detected. Routing directly to: {next_node}")
            return {"next_node": next_node, "past_steps": ["direct_execution"]}

    # 3. If state['plan'] IS empty AND no more tasks
    print("  Plan is empty and tasks are completed. Final Decision: synthesizer")
    return {"next_node": "synthesizer"}


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

        system_prompt = """You are a SQL expert and database analyst. 
        Available Tables:
        {sql_tables}

        The Schema of each table is as follows:
        {sql_schemas}
        
        Your task:
        1. Contextualize the user's latest query by looking at the conversation history. If they say "both" or "them", refer to prior entities discussed.
        2. Translate the user's question into a valid SQLite query, execute read-only operations, and if the user asked you to make changes (write operations), tell them that write operations are not allowed with apologies.
        3. Call 'execute_sql_query' with that query.
        4. Summarize the final result for the user.
        """

        # Get the tables info from SQLAlchemy inspector
        inspector = inspect(db._engine)
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
                    print(f"  Generated SQL Query: {tool_call['args']}")
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
    
    system_prompt = (
        "You are a response synthesizer and helpful AI assistant. "
        "You must answer the user's latest query naturally. "
        "If context information is provided from subagents, use it to answer the query accurately. "
        "If you are greeting or answering casual questions, just respond normally using the conversation history."
    )
    
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
