from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from src.features.agents.nodes import (
    external_worker, 
    internal_worker, 
    orchestrator, 
    planner_node,
    synthesizer, 
    db_analyst_worker, 
    intent_analyzer
)
from src.features.agents.state import AgentState

mem = InMemorySaver()  # For checkpointing and debugging

def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("intent_analyzer", intent_analyzer)
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("planner", planner_node)
    workflow.add_node("internal_search", internal_worker)
    workflow.add_node("external_search", external_worker)
    workflow.add_node("db_analyst", db_analyst_worker)
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
        if score >= 0.6:
            print("  Score >= 0.6 -> Routing to: orchestrator")
            return "orchestrator"
        else:
            print("  Score < 0.6 -> Routing to: external_search")
            return "external_search"

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

    workflow.add_edge("db_analyst", "orchestrator")
    workflow.add_edge("external_search", "orchestrator")
    workflow.add_edge("synthesizer", END)

    # use this when working locally
    # return workflow.compile(checkpointer=mem)
    
    # use this when using `langgraph dev` 
    return workflow.compile()

graph = create_graph()