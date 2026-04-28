from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from src.features.agents.nodes import (
    external_worker, 
    internal_worker, 
    orchestrator, 
    planner_node,
    synthesizer, 
    db_analyst_worker, 
    sql_executor_node,
    intent_analyzer
)
from src.features.agents.state import AgentState

mem = InMemorySaver()  # For checkpointing and debugging
# Add to allowed_msgpack_modules to allow deserialization of custom types
if hasattr(mem, 'serde') and hasattr(mem.serde, 'allowed_msgpack_modules'):
    mem.serde.allowed_msgpack_modules.append('src.features.agents.schemas')

def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("intent_analyzer", intent_analyzer)
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("planner", planner_node)
    workflow.add_node("internal_search", internal_worker)
    workflow.add_node("external_search", external_worker)
    workflow.add_node("db_analyst", db_analyst_worker)
    workflow.add_node("sql_executor_node", sql_executor_node)
    workflow.add_node("synthesizer", synthesizer)

    workflow.set_entry_point("intent_analyzer")

    def route_orchestrator(state: AgentState):
        print("\n" + "="*20 + " [ROUTER: ORCHESTRATOR] " + "="*20)
        path = state.get("next_node", "synthesizer")
        print(f"  Evaluating orchestration path -> Routing to: {path}")
        return path

    def route_internal_search(state: AgentState):
        print("\n" + "="*20 + " [ROUTER: INTERNAL_SEARCH] " + "="*20)
        score = state.get("search_score", 0.0)
        print(f"  Evaluating search score: {score}")
        if score >= 0.5:
            print("  Score >= 0.5 -> Routing to: orchestrator")
            return "orchestrator"
        else:
            print("  Score < 0.5 -> Routing to: external_search")
            return "external_search"

    def route_db_analyst(state: AgentState):
        print("\n" + "="*20 + " [ROUTER: DB_ANALYST] " + "="*20)
        if state.get("requires_confirmation") and state.get("pending_sql"):
            print("  Routing to: sql_executor_node")
            return "sql_executor_node"
        print("  Routing to: orchestrator")
        return "orchestrator"

    workflow.add_edge("intent_analyzer", "orchestrator")

    workflow.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "planner": "planner",
            "internal_search": "internal_search",
            "db_analyst": "db_analyst",
            "external_search": "external_search",
            "synthesizer": "synthesizer"
        }
    )

    workflow.add_edge("planner", "orchestrator")
    
    workflow.add_conditional_edges(
        "internal_search",
        route_internal_search,
        {
            "orchestrator": "orchestrator",
            "external_search": "external_search"
        }
    )

    workflow.add_conditional_edges(
        "db_analyst",
        route_db_analyst,
        {
            "sql_executor_node": "sql_executor_node",
            "orchestrator": "orchestrator"
        }
    )
    workflow.add_edge("sql_executor_node", "orchestrator")
    
    workflow.add_edge("external_search", "orchestrator")
    workflow.add_edge("synthesizer", END)

    # Compile with memory and interrupt
    return workflow.compile(checkpointer=mem, interrupt_before=["sql_executor_node"])
    # return workflow.compile(interrupt_before=["sql_executor_node"])

graph = create_graph()