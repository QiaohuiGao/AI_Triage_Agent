"""
LangGraph 图构建模块 (triage_graph.py)
========================================
本模块负责构建 AI 分诊推理的有向无环图（DAG）。

v2.0 图结构（Design Doc v2.0）:
START -> ParseSymptom -> GraphEnrich -> ESIAssess -> Clarify? -> RetrieveDocs
      -> ReasonReflect -> VoteConfidence -> FallbackRoute -> END

每个节点代表一个推理步骤：
1. ParseSymptom: 从患者描述中提取症状实体 + SNOMED 映射
2. GraphEnrich: 使用 Neo4j 图谱丰富症状上下文 (v2.0 新增)
3. ESIAssess: ESI 五级分诊评估 (v2.0 新增)
4. Clarify: 动态追问节点，基于 Schmitt-Thompson 协议 (v2.0 新增)
5. RetrieveDocs: 从向量数据库检索相关医疗文档
6. ReasonReflect: 基于检索到的文档进行推理和反思
7. VoteConfidence: 聚合多次推理结果，计算置信度和一致性
8. FallbackRoute: 根据 ESI 等级和置信度生成最终分诊建议

使用 LangGraph 的 StateGraph 来管理节点间的状态流转。
"""

from langgraph.graph import StateGraph, START, END
from app.schemas import GraphState
from typing import Literal

# ========== 原有节点 ==========
from .nodes.parse_symptom import parse_symptom
from .nodes.retrieve_docs import retrieve_docs
from .nodes.reason_reflect import reason_reflect
from .nodes.vote_confidence import vote_confidence
from .nodes.fallback_route import fallback_route

# ========== v2.0 新增节点 ==========
from .nodes.clarifier import clarify_node, should_clarify

# v2.0 Logic imports
from app.logic.esi_engine import ESIEngine, calculate_esi
from app.logic.graph_service import get_graph_service, enrich_with_graph

# v2.1 Clinical Rules Reasoning
from app.logic.clinical_rules_reasoner import reason_with_rules, ReasoningResult


# ========== v2.0 新增节点函数 ==========

def graph_enrich_node(state: GraphState) -> GraphState:
    """
    图丰富节点 - 使用 Neo4j SNOMED 图谱丰富症状上下文

    从 ParseSymptom 获取的 entities 中提取 SNOMED codes，
    通过 Neo4j 查询获取：
    - 解剖部位 (Finding Site)
    - 病理形态 (Associated Morphology)
    - 祖先类别 (ISA hierarchy)
    - 风险关联 (Risk paths)
    """
    entities = state.entities or []

    if not entities:
        return state

    try:
        graph_service = get_graph_service()

        # 收集所有症状的图上下文
        combined_context = {
            "finding_sites": [],
            "morphologies": [],
            "ancestors": [],
            "risk_associations": [],
            "related_procedures": []
        }

        for entity in entities:
            sctid = entity.get("sctid")
            if not sctid:
                continue

            # 获取每个症状的图上下文
            context = graph_service.get_concept_context(sctid)

            # 合并上下文
            combined_context["finding_sites"].extend(context.finding_sites)
            combined_context["morphologies"].extend(context.morphologies)
            combined_context["ancestors"].extend(context.ancestors)

            # 获取风险关联
            risks = graph_service.find_risk_associations(sctid)
            combined_context["risk_associations"].extend(risks)

            # 获取相关操作（用于资源估计）
            procedures = graph_service.get_related_procedures(sctid)
            combined_context["related_procedures"].extend(procedures)

        # 去重
        for key in combined_context:
            seen = set()
            unique = []
            for item in combined_context[key]:
                item_id = item.get("sctid") or str(item)
                if item_id not in seen:
                    seen.add(item_id)
                    unique.append(item)
            combined_context[key] = unique

        state.graph_context = combined_context
        state.risk_associations = combined_context["risk_associations"]

    except Exception as e:
        # 图查询失败不应阻断流程，记录错误但继续
        print(f"[GraphEnrich] Warning: Neo4j query failed: {e}")
        state.graph_context = None

    return state


def esi_assess_node(state: GraphState) -> GraphState:
    """
    ESI 评估节点 - 执行 ESI 五级分诊评估

    基于 ESI v4 的四个决策点：
    - Decision A: 是否需要立即抢救？(ESI 1)
    - Decision B: 是否属于高危情况？(ESI 2)
    - Decision C: 需要多少医疗资源？(ESI 3-5)
    - Decision D: 生命体征是否异常？(可能升级)
    """
    entities = state.entities or []
    vitals = state.vitals
    graph_context = state.graph_context

    if not entities:
        return state

    try:
        # 构建症状列表供 ESI 引擎使用
        symptoms = []
        for entity in entities:
            symptoms.append({
                "symptom": entity.get("symptom", ""),
                "sctid": entity.get("sctid", ""),
                "severity": entity.get("severity", "moderate"),
                "fsn": entity.get("fsn", entity.get("symptom", ""))
            })

        # 执行 ESI 评估
        esi_assessment = calculate_esi(symptoms, vitals, graph_context)

        # 更新状态
        state.esi_assessment = {
            "level": esi_assessment.level.value,
            "decision_point": esi_assessment.decision_point,
            "rationale": esi_assessment.rationale,
            "red_flags": esi_assessment.red_flags,
            "requires_clarification": esi_assessment.requires_clarification,
            "clarification_questions": esi_assessment.clarification_questions,
            "confidence": esi_assessment.confidence,
            "resource_estimate": esi_assessment.resource_estimate
        }
        state.esi_level = esi_assessment.level.value
        state.red_flags = esi_assessment.red_flags

        # 如果 ESI 评估需要澄清，设置追问标志
        if esi_assessment.requires_clarification:
            state.needs_clarification = True
            state.clarification_questions = esi_assessment.clarification_questions

    except Exception as e:
        print(f"[ESIAssess] Warning: ESI assessment failed: {e}")
        # 设置默认值
        state.esi_level = 3
        state.esi_assessment = {
            "level": 3,
            "decision_point": "C",
            "rationale": "Default assessment due to error",
            "confidence": 0.5
        }

    return state


def clinical_rules_reason_node(state: GraphState) -> GraphState:
    """
    临床规则推理节点 - 基于Neo4j临床决策规则进行确定性推理

    使用 ClinicalRulesReasoner 查询匹配的临床规则:
    - Canadian CT Head Rule (TBI)
    - HEART Score (ACS)
    - Wells Criteria / PERC Rule (PE)
    - FAST / NIH Stroke Scale (Stroke)
    - Stanford Classification (Aortic Dissection)

    输出:
    - matched_rules: 匹配的规则列表
    - rule_based_questions: 基于规则的追问问题
    - recommended_actions: 推荐的临床动作
    """
    entities = state.entities or []

    if not entities:
        return state

    try:
        # 收集所有症状的 SNOMED codes 和关键词
        symptom_sctids = []
        symptom_keywords = []
        max_severity = "mild"
        severity_order = {"mild": 0, "moderate": 1, "severe": 2}

        for entity in entities:
            sctid = entity.get("sctid")
            if sctid:
                symptom_sctids.append(sctid)

            symptom = entity.get("symptom", "")
            if symptom:
                symptom_keywords.append(symptom.lower())

            # 取最高严重程度
            sev = entity.get("severity", "moderate")
            if severity_order.get(sev, 1) > severity_order.get(max_severity, 1):
                max_severity = sev

        # 执行规则推理
        result: ReasoningResult = reason_with_rules(
            symptom_sctids=symptom_sctids,
            symptom_keywords=symptom_keywords,
            severity=max_severity
        )

        # 更新状态
        state.clinical_rules_result = {
            "matched_rules": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "risk_level": r.risk_level,
                    "guideline_source": r.guideline_source,
                    "coverage": r.coverage,
                    "matched_criteria": r.matched_criteria,
                    "missing_criteria": r.missing_criteria,
                    "action": r.action,
                    "evidence_text": r.evidence_text
                }
                for r in result.matched_rules
            ],
            "highest_risk": result.highest_risk,
            "recommended_actions": result.recommended_actions,
            "reasoning_trace": result.reasoning_trace,
            "confidence": result.confidence
        }

        # 合并规则追问问题到状态
        if result.clarifying_questions:
            existing_questions = state.clarification_questions or []
            # 避免重复
            existing_ids = {q.get("question_id") for q in existing_questions}
            for q in result.clarifying_questions:
                if q.get("question_id") not in existing_ids:
                    existing_questions.append(q)
            state.clarification_questions = existing_questions

            # 如果有高优先级问题且未超过追问轮数，标记需要追问
            high_priority_qs = [q for q in result.clarifying_questions if q.get("priority", 99) <= 2]
            if high_priority_qs and not state.needs_clarification:
                state.needs_clarification = True

        # 如果规则推理发现更高风险，可能需要升级 ESI
        if result.highest_risk == "CRITICAL" and state.esi_level and state.esi_level > 1:
            state.esi_level = 1
            if state.esi_assessment:
                state.esi_assessment["level"] = 1
                state.esi_assessment["rationale"] += f" [Upgraded by clinical rule: {result.matched_rules[0].rule_name if result.matched_rules else 'CRITICAL risk'}]"

        elif result.highest_risk == "HIGH" and state.esi_level and state.esi_level > 2:
            state.esi_level = 2
            if state.esi_assessment:
                state.esi_assessment["level"] = 2
                state.esi_assessment["rationale"] += " [Upgraded by clinical rule: HIGH risk]"

    except Exception as e:
        print(f"[ClinicalRulesReason] Warning: Rule reasoning failed: {e}")
        state.clinical_rules_result = None

    return state


def clarify_route(state: GraphState) -> Literal["Clarify", "RetrieveDocs"]:
    """
    条件路由函数 - 决定是否需要追问

    如果 ESI 评估标记需要澄清且未超过最大追问轮数，进入追问节点
    """
    if should_clarify(state):
        return "Clarify"
    return "RetrieveDocs"


def post_clarify_route(state: GraphState) -> Literal["ESIAssess", "RetrieveDocs"]:
    """
    追问后路由函数 - 决定追问后的下一步

    如果追问获得了新信息（clarification_response），重新评估 ESI
    否则继续进入文档检索
    """
    if state.clarification_response:
        return "ESIAssess"
    return "RetrieveDocs"


# ========== 图构建函数 ==========

def build_triage_graph():
    """
    构建 v2.0 分诊推理图

    集成 ESI 引擎、Neo4j 图推理、动态追问等新功能

    返回:
        StateGraph: 配置好的状态图对象，需要调用 .compile() 方法编译后使用
    """
    # ========== 创建状态图 ==========
    graph = StateGraph(GraphState)

    # ========== 添加节点 ==========
    # 原有节点
    graph.add_node("ParseSymptom", parse_symptom)      # 解析症状 + SNOMED 映射
    graph.add_node("RetrieveDocs", retrieve_docs)      # 检索文档
    graph.add_node("ReasonReflect", reason_reflect)    # 推理反思
    graph.add_node("VoteConfidence", vote_confidence)  # 投票聚合
    graph.add_node("FallbackRoute", fallback_route)    # 路由决策

    # v2.0 新增节点
    graph.add_node("GraphEnrich", graph_enrich_node)   # 图丰富
    graph.add_node("ESIAssess", esi_assess_node)       # ESI 评估
    graph.add_node("Clarify", clarify_node)            # 动态追问

    # v2.1 临床规则推理节点
    graph.add_node("ClinicalRulesReason", clinical_rules_reason_node)  # 规则推理

    # ========== 定义有向边 ==========
    # 主流程
    graph.add_edge(START, "ParseSymptom")              # 开始 -> 解析症状
    graph.add_edge("ParseSymptom", "GraphEnrich")      # 解析症状 -> 图丰富
    graph.add_edge("GraphEnrich", "ESIAssess")         # 图丰富 -> ESI 评估
    graph.add_edge("ESIAssess", "ClinicalRulesReason") # ESI 评估 -> 规则推理

    # 条件边：规则推理后决定是否追问
    graph.add_conditional_edges(
        "ClinicalRulesReason",
        clarify_route,
        {
            "Clarify": "Clarify",
            "RetrieveDocs": "RetrieveDocs"
        }
    )

    # 追问后的路由（如果有回答则重新评估 ESI，否则继续）
    graph.add_conditional_edges(
        "Clarify",
        post_clarify_route,
        {
            "ESIAssess": "ESIAssess",
            "RetrieveDocs": "RetrieveDocs"
        }
    )

    # 后续流程
    graph.add_edge("RetrieveDocs", "ReasonReflect")    # 检索 -> 推理
    graph.add_edge("ReasonReflect", "VoteConfidence")  # 推理 -> 投票
    graph.add_edge("VoteConfidence", "FallbackRoute")  # 投票 -> 路由
    graph.add_edge("FallbackRoute", END)               # 路由 -> 结束

    return graph


def build_triage_graph_v1():
    """
    构建 v1.0 分诊推理图（保留兼容性）

    原始简单版本，不包含 ESI 和图推理

    返回:
        StateGraph: 配置好的状态图对象
    """
    graph = StateGraph(GraphState)

    graph.add_node("ParseSymptom", parse_symptom)
    graph.add_node("RetrieveDocs", retrieve_docs)
    graph.add_node("ReasonReflect", reason_reflect)
    graph.add_node("VoteConfidence", vote_confidence)
    graph.add_node("FallbackRoute", fallback_route)

    graph.add_edge(START, "ParseSymptom")
    graph.add_edge("ParseSymptom", "RetrieveDocs")
    graph.add_edge("RetrieveDocs", "ReasonReflect")
    graph.add_edge("ReasonReflect", "VoteConfidence")
    graph.add_edge("VoteConfidence", "FallbackRoute")
    graph.add_edge("FallbackRoute", END)

    return graph