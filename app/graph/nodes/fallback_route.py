"""
回退路由节点 (fallback_route.py)
===============================
本节点负责生成最终的分诊建议，根据置信度和规则进行路由决策。

v2.0 更新：集成 ESI 评估结果，基于 ESI 等级进行路由

功能：
- 检查 ESI Level 1-2（最高优先级，急诊处理）
- 检查红色标志词（red flags），直接路由到急诊科
- 评估置信度和一致性，如果过低则保守路由到初级保健
- 根据疾病条件查找路由表，生成科室建议
- 生成最终的分诊输出（final_output）

路由规则优先级：
1. ESI Level 1: 立即抢救 -> Emergency (ER)
2. ESI Level 2: 高危紧急 -> Emergency (Urgent)
3. 红色标志词规则 -> Emergency (ER)
4. 低置信度/低一致性规则 -> Primary Care (Routine)
5. ESI Level 3-5: 基于路由表
6. 正常路由规则（基于路由表）

输入：GraphState（包含所有前面节点的输出）
输出：GraphState.final_output
"""

from app.config import AGREEMENT_MIN, CONFIDENCE_MIN, RED_FLAG_TERMS
from app.schemas import GraphState  # 导入 GraphState 类型

# ========== 路由表 ==========
# 将疾病条件映射到科室和紧急程度
# 格式：{疾病名称: (科室, 紧急程度)}
ROUTING_TABLE = {
    "Angina": ("Cardiology", "Urgent"),              # 心绞痛 -> 心内科（紧急）
    "Pulmonary embolism": ("Emergency", "ER"),       # 肺栓塞 -> 急诊科（急诊）
    "Muscle strain": ("Orthopedics", "Routine"),     # 肌肉拉伤 -> 骨科（常规）
    "Undifferentiated complaint": ("Primary Care", "Routine")  # 未分化主诉 -> 初级保健（常规）
}

# ========== ESI 等级到紧急程度映射 ==========
ESI_URGENCY_MAP = {
    1: "ER",         # 立即抢救
    2: "ER",         # 高危紧急
    3: "Urgent",     # 紧急
    4: "Routine",    # 较紧急
    5: "Routine"     # 非紧急
}

# ========== ESI 等级到默认科室映射 ==========
ESI_DEPARTMENT_MAP = {
    1: "Emergency",       # ESI 1 -> 急诊抢救
    2: "Emergency",       # ESI 2 -> 急诊
    3: None,              # ESI 3 -> 根据条件路由
    4: None,              # ESI 4 -> 根据条件路由
    5: "Primary Care"     # ESI 5 -> 初级保健
}

def fallback_route(state: GraphState) -> GraphState:
    """
    回退路由节点 (v2.0)

    根据 ESI 等级、置信度、一致性和规则生成最终的分诊建议。
    实现多层路由策略：
    1. ESI Level 1-2 检查（最高优先级）
    2. 红色标志词检查
    3. 低置信度/低一致性检查（保守路由）
    4. 正常路由（基于路由表）

    参数:
        state: GraphState 对象，包含所有前面节点的输出

    返回:
        更新后的 GraphState，包含 final_output 字段
    """
    # ========== 读取输入数据 ==========
    patient_input = getattr(state, "patient_input", {}) or {}
    text = patient_input.get("text", "").lower()

    # ========== 读取 ESI 评估结果 (v2.0) ==========
    esi_assessment = getattr(state, "esi_assessment", None) or {}
    esi_level = esi_assessment.get("level") or getattr(state, "esi_level", None)
    esi_rationale = esi_assessment.get("rationale", "")
    esi_red_flags = esi_assessment.get("red_flags", []) or getattr(state, "red_flags", [])
    esi_confidence = esi_assessment.get("confidence", 0.0)

    # ========== 读取投票结果 ==========
    vote = getattr(state, "voting_result", None)
    if not vote:
        vote = {"avg_confidence": 0.0, "agreement": 0.0}
    avg_conf = vote.get("avg_confidence", 0.0)
    agreement = vote.get("agreement", 0.0)

    # ========== 读取推理运行结果 ==========
    runs = getattr(state, "reasoning_runs", []) or []
    conds = []
    if runs and isinstance(runs[0], dict):
        conds = runs[0].get("conditions", [])
    conds = conds or ["Undifferentiated complaint"]

    # ========== 路由规则0：ESI Level 1 检查（立即抢救）==========
    if esi_level == 1:
        state.final_output = {
            "suggested_department": "Emergency",
            "urgency": "ER",
            "confidence": max(esi_confidence, 0.99),
            "agreement": agreement,
            "esi_level": 1,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": f"ESI Level 1 - Immediate Resuscitation: {esi_rationale}",
            "red_flags": esi_red_flags,
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ========== 路由规则1：ESI Level 2 检查（高危紧急）==========
    if esi_level == 2:
        state.final_output = {
            "suggested_department": "Emergency",
            "urgency": "ER",
            "confidence": max(esi_confidence, 0.95),
            "agreement": agreement,
            "esi_level": 2,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": f"ESI Level 2 - High Risk Emergency: {esi_rationale}",
            "red_flags": esi_red_flags,
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ========== 路由规则2：红色标志词检查 ==========
    if any(t in text for t in RED_FLAG_TERMS):
        state.final_output = {
            "suggested_department": "Emergency",
            "urgency": "ER",
            "confidence": 0.99,
            "agreement": agreement,
            "esi_level": esi_level or 2,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": "Red-flag safety rule triggered.",
            "red_flags": esi_red_flags,
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ========== 路由规则3：低置信度/低一致性检查 ==========
    if avg_conf < CONFIDENCE_MIN or agreement < AGREEMENT_MIN:
        # 即使低置信度，如果 ESI 较高也要考虑
        if esi_level and esi_level <= 3:
            dept = "Emergency" if esi_level <= 2 else "Urgent Care"
            urg = ESI_URGENCY_MAP.get(esi_level, "Urgent")
        else:
            dept = "Primary Care"
            urg = "Routine"

        state.final_output = {
            "suggested_department": dept,
            "urgency": urg,
            "confidence": avg_conf,
            "agreement": agreement,
            "esi_level": esi_level,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": f"Conservative routing due to low confidence/agreement. ESI: {esi_level or 'N/A'}",
            "red_flags": esi_red_flags,
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ========== 路由规则4：基于 ESI Level 3-5 的正常路由 ==========
    # 首先检查 ESI 指定的默认科室
    if esi_level and ESI_DEPARTMENT_MAP.get(esi_level):
        dept = ESI_DEPARTMENT_MAP[esi_level]
        urg = ESI_URGENCY_MAP.get(esi_level, "Routine")
    else:
        # 根据疾病条件查找路由表
        dept, urg = ROUTING_TABLE.get(conds[0], ("Primary Care", "Routine"))

        # 如果 ESI 等级较高但路由表给出较低紧急度，以 ESI 为准
        if esi_level and esi_level <= 3 and urg == "Routine":
            urg = "Urgent"

    state.final_output = {
        "suggested_department": dept,
        "urgency": urg,
        "confidence": avg_conf,
        "agreement": agreement,
        "esi_level": esi_level,
        "final_conditions": [
            {"condition": c, "confidence": avg_conf} for c in conds[:3]
        ],
        "rationale": f"{runs[0].get('hypothesis', 'Triage rationale.') if runs else 'Triage rationale.'} (ESI Level: {esi_level or 'N/A'})",
        "red_flags": esi_red_flags,
        "evidence": getattr(state, "retrieved_docs", [])
    }

    return state