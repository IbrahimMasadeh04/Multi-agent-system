from langgraph.graph import END, StateGraph

from src.features.agents.state import AgentState  # type: ignore
from src.features.agents.file_generator_nodes import (  # type: ignore
    filegen_router,
    template_manager_node,
    template_filler_node,
    template_qa_node,
    # template_generator_node,
    agent_orchestrator_node,
)


def create_file_generator_subgraph():
    """
    Creates a nested LangGraph subgraph for file generation operations.
    
    Flow:
        filegen_router -> [sub-agent] -> filegen_router -> ... -> done (END)
    
    The filegen_router loops back after each sub-agent completes,
    enabling multi-step flows (e.g., list -> get -> fill).
    Routes to END when the task is complete ('done').
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("filegen_router", filegen_router)
    workflow.add_node("template_manager", template_manager_node)
    workflow.add_node("template_filler", template_filler_node)
    workflow.add_node("template_qa", template_qa_node)
    # workflow.add_node("template_generator", template_generator_node)
    workflow.add_node("agent_orchestrator", agent_orchestrator_node)

    # Entry point
    workflow.set_entry_point("filegen_router")

    # Router conditional edges
    def route_filegen(state: AgentState):
        print("\n" + "="*20 + " [ROUTER: FILEGEN] " + "="*20)
        path = state.get("filegen_next", "done")
        print(f"  Evaluating filegen path -> Routing to: {path}")
        return path

    workflow.add_conditional_edges(
        "filegen_router",
        route_filegen,
        {
            "template_manager": "template_manager",
            "template_filler": "template_filler",
            "template_qa": "template_qa",
            # "template_generator": "template_generator",
            "agent_orchestrator": "agent_orchestrator",
            "done": END,
        }
    )

    # All sub-agents loop back to filegen_router for multi-step flows
    workflow.add_edge("template_manager", "filegen_router")
    workflow.add_edge("template_filler", "filegen_router")
    workflow.add_edge("template_qa", "filegen_router")
    # workflow.add_edge("template_generator", "filegen_router")
    workflow.add_edge("agent_orchestrator", "filegen_router")

    return workflow.compile()


file_generator_subgraph = create_file_generator_subgraph()
