from langgraph.graph import StateGraph, START, END
from app.schemas import GraphState
from .nodes.parse_symptom import parse_symptom
from .nodes.retrieve_docs import retrieve_docs
from .nodes.reason_reflect import reason_reflect
from .nodes.vote_confidence import vote_confidence
from .nodes.fallback_route import fallback_route


def build_triage_graph():
    # ✅ 正确写法：传入状态类 GraphState，而不是函数
    graph = StateGraph(GraphState)

    # ✅ 定义节点
    graph.add_node("ParseSymptom", parse_symptom)
    graph.add_node("RetrieveDocs", retrieve_docs)
    graph.add_node("ReasonReflect", reason_reflect)
    graph.add_node("VoteConfidence", vote_confidence)
    graph.add_node("FallbackRoute", fallback_route)

    # ✅ 定义有向边（从 START 开始）
    graph.add_edge(START, "ParseSymptom")
    graph.add_edge("ParseSymptom", "RetrieveDocs")
    graph.add_edge("RetrieveDocs", "ReasonReflect")
    graph.add_edge("ReasonReflect", "VoteConfidence")
    graph.add_edge("VoteConfidence", "FallbackRoute")
    graph.add_edge("FallbackRoute", END)

    return graph