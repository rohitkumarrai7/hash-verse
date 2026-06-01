from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from graph.checkpointer import get_checkpointer
from graph.nodes import (
    classify_intent_node,
    load_metadata_node,
    retrieve_node,
)
from graph.state import AgentState
from services.vectorstore import VectorStore


def build_retrieve_node(vector_store: VectorStore):
    def _node(state: dict[str, Any]) -> dict[str, Any]:
        return retrieve_node(state, vector_store)

    return _node


def build_graph(vector_store: VectorStore):
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("load_metadata", load_metadata_node)
    graph.add_node("retrieve", build_retrieve_node(vector_store))

    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "load_metadata")
    graph.add_edge("load_metadata", "retrieve")
    graph.add_edge("retrieve", END)

    return graph.compile(checkpointer=get_checkpointer())
