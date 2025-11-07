"""
LangGraph 图构建模块 (triage_graph.py)
========================================
本模块负责构建 AI 分诊推理的有向无环图（DAG）。

图结构：
START -> ParseSymptom -> RetrieveDocs -> ReasonReflect -> VoteConfidence -> FallbackRoute -> END

每个节点代表一个推理步骤：
1. ParseSymptom: 从患者描述中提取症状实体
2. RetrieveDocs: 从向量数据库检索相关医疗文档
3. ReasonReflect: 基于检索到的文档进行推理和反思
4. VoteConfidence: 聚合多次推理结果，计算置信度和一致性
5. FallbackRoute: 根据置信度和规则生成最终分诊建议

使用 LangGraph 的 StateGraph 来管理节点间的状态流转。
"""

from langgraph.graph import StateGraph, START, END
from app.schemas import GraphState
from .nodes.parse_symptom import parse_symptom
from .nodes.retrieve_docs import retrieve_docs
from .nodes.reason_reflect import reason_reflect
from .nodes.vote_confidence import vote_confidence
from .nodes.fallback_route import fallback_route

# 在 build_triage_graph() 里把 RetrieveDocs 这个节点的可调用设为 retrieve_docs
# 例如：
# graph.add_node("RetrieveDocs", retrieve_docs)


def build_triage_graph():
    """
    构建分诊推理图
    创建并配置 LangGraph 状态图，定义节点和边的连接关系。
    图使用 GraphState 作为状态容器，所有节点共享此状态。
    
    返回:
        StateGraph: 配置好的状态图对象，需要调用 .compile() 方法编译后使用
    """
    # ========== 创建状态图 ==========
    # 使用 GraphState 作为状态类型，确保类型安全
    graph = StateGraph(GraphState)

    # ========== 添加节点 ==========
    # 每个节点都是一个函数，接收 GraphState 并返回更新后的 GraphState
    graph.add_node("ParseSymptom", parse_symptom)      # 节点1: 解析症状
    graph.add_node("RetrieveDocs", retrieve_docs)      # 节点2: 检索文档
    graph.add_node("ReasonReflect", reason_reflect)    # 节点3: 推理反思
    graph.add_node("VoteConfidence", vote_confidence)  # 节点4: 投票聚合
    graph.add_node("FallbackRoute", fallback_route)    # 节点5: 路由决策

    # ========== 定义有向边 ==========
    # 定义节点之间的执行顺序和数据流向
    graph.add_edge(START, "ParseSymptom")              # 从开始节点连接到解析症状节点
    graph.add_edge("ParseSymptom", "RetrieveDocs")     # 解析完成后检索文档
    graph.add_edge("RetrieveDocs", "ReasonReflect")    # 检索完成后进行推理
    graph.add_edge("ReasonReflect", "VoteConfidence")  # 推理完成后进行投票聚合
    graph.add_edge("VoteConfidence", "FallbackRoute")  # 投票完成后进行路由决策
    graph.add_edge("FallbackRoute", END)               # 路由完成后结束

    return graph