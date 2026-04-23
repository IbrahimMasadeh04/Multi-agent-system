from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
# from langchain_community.agent_toolkits.sql.base import create_sql_agent

from src.features.db_analyst.tools import execute_sql_query
from src.features.agents.state import AgentState
from src.features.ingestion.service import search_internal_docs_with_score
from src.helper.config import get_settings
from src.helper.shared import _message_text, _get_llm
from src.features.db_analyst.service import _get_sql_toolkit

##########################
#      ORCHESTRATOR      #
##########################
async def orchestrator(state: AgentState):
    """
    Orchestrator uses an LLM to decide the next step based on search results and threshold.
    """

    llm = _get_llm(TEMPERATURE=0.0)
    
    # Use helper to extract text safely from any message format
    last_message = _message_text(state['messages'][-1])

    
    system_prompt = """You are the master orchestrator for Venom System.
    Route the query to the correct worker:
    1. 'internal_search': Use this for PDFs, rules, text documents, and general context from files.
    2. 'db_analyst': Use this ONLY for structured data: inventory, devices list, pricing, sales, and anything requiring SQL counting or filtering.
    3. 'synthesizer': Use this when you have gathered enough information to provide a final response.

    Query: {query}
    Respond with ONLY the worker name."""

    response = llm.invoke(system_prompt.format(query=last_message))
    decision = response.content.strip().lower()
    
    return {"next_node": decision}


#############################
#      INTERNAL WORKER      #
#############################
async def internal_worker(state: AgentState):
    """
    Subagent for internal PDF/vector knowledge search.
    """
    user_query = _message_text(state["messages"][0])
    try:
        combined_text, best_score = await search_internal_docs_with_score(user_query)
        return {
            "messages": [AIMessage(content=f"Internal Search Results (Score: {best_score}): {combined_text}")],
            "search_score": best_score
        }
    except Exception as exc:
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
    user_query = _message_text(state["messages"][0])
    settings = get_settings()
    if not settings.TAVILY_API_KEY:
        return {
            "messages": [AIMessage(content="External Search Results: TAVILY_API_KEY missing.")],
            "next_node": "orchestrator"
        }

    try:
        search = TavilySearch(max_results=2, tavily_api_key=settings.TAVILY_API_KEY)
        results = await search.ainvoke(user_query)
        return {
            "messages": [AIMessage(content=f"External Search Results: {results}")],
            "next_node": "orchestrator"
        }
    except Exception as exc:
        return {
            "messages": [AIMessage(content=f"External Search Results: (Error) {exc}")],
            "next_node": "orchestrator"
        }


##########################
#      DB WORKER         #
##########################
async def db_analyst_worker(state: AgentState):

    try:
        query = _message_text(state["messages"][-1])
        print(f"DEBUG: DB Analyst received query: {query}")

        tools = [execute_sql_query]
        llm_with_tools = _get_llm(TEMPERATURE=0.0).bind_tools(tools)

        system_prompt = """You are a SQL expert. 
        Available Tables:
        {sql_tables}

        The Schema of each table is as follows:
        {sql_schemas}
        
        Your task:
        1. Translate the user's question into a valid SQLite query, execute a read-only operations, and if the user asked you to make changes (write operations), tell them that write operations are not allowed ,with apologies.
        2. Call 'execute_sql_query' with that query.
        3. Summarize the final result for the user.
        """

        # Get the tables info from the toolkit
        toolkit = _get_sql_toolkit()
        toolkit_tools = toolkit.get_tools()
        list_tables_tool = next((tool for tool in toolkit_tools if tool.name == "sql_db_list_tables"), None)
        schema_tool = next((tool for tool in toolkit_tools if tool.name == "sql_db_schema"), None)
        
        if list_tables_tool:
            # Execute the tool to get the actual list of tables
            tables = list_tables_tool.run("")
        else:
            tables = "No tables found or tool unavailable."

        if schema_tool and tables:
            schemas = schema_tool.run(tables)
        else:
            schemas = "No schema information available."

        print(f"DEBUG: DB Tables: {tables}")

        response = await llm_with_tools.ainvoke([
            SystemMessage(content=system_prompt.format(sql_tables=tables, sql_schemas=schemas)),
            HumanMessage(content=query)
        ])

        print(f"DEBUG: DB Analyst LLM Response: {response.content}")

        # Check if model called a tool
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call['name'] == 'execute_sql_query':
                    tool_result = execute_sql_query.invoke(tool_call['args'])
                    print(f"DEBUG: Tool Result: {tool_result}")
                    # Summarize the result instead of just returning raw string
                    summary_prompt = "Summarize the following SQL results for the user: {results}"
                    summary_res = await _get_llm().ainvoke([
                        SystemMessage(content="You are a helpful assistant."),
                        HumanMessage(content=summary_prompt.format(results=tool_result))
                    ])
                    return {
                        "messages": [AIMessage(content=summary_res.content)],
                        "next_node": "synthesizer"
                    }

        if not response.content or response.content.strip() == "":
            return {
                "messages": [AIMessage(content="I couldn't find a way to answer that using the database.")],
                "next_node": "synthesizer"
            }

        return {
            "messages": [AIMessage(content=response.content)],
            "next_node": "synthesizer"
        }

    except Exception as exc:
        print(f"DEBUG: DB Analyst Error: {exc}")
        return {
            "messages": [AIMessage(content=f"DB Analyst Results: (Error) {exc}")],
            "next_node": "orchestrator"
        }


##########################
#      SYNTHESIZER       #
##########################
async def synthesizer(state: AgentState):
    """
    Takes all inputs and produces a logical, refined response.
    """
    llm = _get_llm()
    
    context_msgs = [m for m in state["messages"] if isinstance(m, AIMessage)]
    context = "\n\n".join([_message_text(m) for m in context_msgs])
    
    system_prompt = (
        "You are a response synthesizer. Your role is to take various pieces of information "
        "provided by subagents and refine them into a logical, cohesive final response for the user. "
        "Ensure the response follows a natural, logical order regardless of the input order. "
        "Summarize and refine for clarity."
    )
    
    final_response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User Query: {_message_text(state['messages'][0])}\n\nInformation collected:\n{context}")
    ])
    
    return {"messages": [final_response]}
