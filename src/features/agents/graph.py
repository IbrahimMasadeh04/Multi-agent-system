from langgraph.graph import END, StateGraph

from src.features.agents.nodes import external_worker, internal_worker, orchestrator, synthesizer, db_analyst_worker
from src.features.agents.state import AgentState


def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("internal_search", internal_worker)
    workflow.add_node("external_search", external_worker)
    workflow.add_node("db_analyst", db_analyst_worker)
    workflow.add_node("synthesizer", synthesizer)

    workflow.set_entry_point("orchestrator")

    def route_orchestrator(state: AgentState):
        return state.get("next_node", "synthesizer")

    def route_internal_search(state: AgentState):
        score = state.get("search_score", 0.0)
        if score >= 0.5:
            return "orchestrator"
        else:
            return "external_search"

    workflow.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "internal_search": "internal_search",
            "db_analyst": "db_analyst",
            "synthesizer": "synthesizer"
        }
    )

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

    return workflow.compile()

graph = create_graph()