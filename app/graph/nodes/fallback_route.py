"""
回退路由节点 (fallback_route.py)
===============================
本节点负责生成最终的分诊建议，根据置信度和规则进行路由决策。

功能：
- 检查红色标志词（red flags），直接路由到急诊科
- 评估置信度和一致性，如果过低则保守路由到初级保健
- 根据疾病条件查找路由表，生成科室建议
- 生成最终的分诊输出（final_output）

路由规则优先级：
1. 红色标志词规则（最高优先级）
2. 低置信度/低一致性规则（保守路由）
3. 正常路由规则（基于路由表）

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

def fallback_route(state: GraphState) -> GraphState:
    """
    回退路由节点
    
    根据置信度、一致性和规则生成最终的分诊建议。
    实现三层路由策略：
    1. 红色标志词检查（最高优先级）
    2. 低置信度/低一致性检查（保守路由）
    3. 正常路由（基于路由表）
    
    参数:
        state: GraphState 对象，包含所有前面节点的输出
    
    返回:
        更新后的 GraphState，包含 final_output 字段
    """
    # ========== 读取输入数据 ==========
    # 从 GraphState 中安全地读取各种输入数据
    patient_input = getattr(state, "patient_input", {}) or {}
    text = patient_input.get("text", "").lower()  # 患者症状描述（小写）

    # ========== 读取投票结果 ==========
    # 从 VoteConfidence 节点获取投票聚合结果
    vote = getattr(state, "voting_result", None)
    if not vote:
        # 如果没有投票结果，使用默认值
        vote = {"avg_confidence": 0.0, "agreement": 0.0}
    avg_conf = vote.get("avg_confidence", 0.0)  # 平均置信度
    agreement = vote.get("agreement", 0.0)      # 一致性

    # ========== 读取推理运行结果 ==========
    # 从 ReasonReflect 节点获取推理运行结果
    runs = getattr(state, "reasoning_runs", []) or []
    conds = []
    if runs and isinstance(runs[0], dict):
        # 提取可能的疾病条件
        conds = runs[0].get("conditions", [])
    conds = conds or ["Undifferentiated complaint"]  # 如果没有条件，使用默认值

    # ========== 路由规则1：红色标志词检查 ==========
    # 如果患者描述包含红色标志词（如胸痛、呼吸困难），直接路由到急诊科
    # 这是最高优先级的规则，用于识别紧急情况
    if any(t in text for t in RED_FLAG_TERMS):
        state.final_output = {
            "suggested_department": "Emergency",      # 建议科室：急诊科
            "urgency": "ER",                          # 紧急程度：急诊
            "confidence": 0.99,                       # 置信度：0.99（高置信度）
            "agreement": agreement,                   # 一致性
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],  # 可能的疾病
            "rationale": "Red-flag safety rule triggered.",  # 推理依据
            "evidence": getattr(state, "retrieved_docs", [])  # 检索到的医疗文档证据
        }
        return state

    # ========== 路由规则2：低置信度/低一致性检查 ==========
    # 如果置信度或一致性低于阈值，采用保守路由策略
    # 将患者路由到初级保健，而不是专科科室
    if avg_conf < CONFIDENCE_MIN or agreement < AGREEMENT_MIN:
        state.final_output = {
            "suggested_department": "Primary Care",   # 建议科室：初级保健
            "urgency": "Routine",                      # 紧急程度：常规
            "confidence": avg_conf,                    # 置信度
            "agreement": agreement,                    # 一致性
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],  # 可能的疾病
            "rationale": "Conservative routing due to low confidence/agreement.",  # 推理依据
            "evidence": getattr(state, "retrieved_docs", [])  # 检索到的医疗文档证据
        }
        return state

    # ========== 路由规则3：正常路由 ==========
    # 根据疾病条件查找路由表，生成科室建议
    # 如果疾病不在路由表中，默认路由到初级保健
    dept, urg = ROUTING_TABLE.get(conds[0], ("Primary Care", "Routine"))
    
    state.final_output = {
        "suggested_department": dept,                 # 建议科室
        "urgency": urg,                               # 紧急程度
        "confidence": avg_conf,                       # 置信度
        "agreement": agreement,                       # 一致性
        "final_conditions": [
            {"condition": c, "confidence": avg_conf} for c in conds[:3]  # 前3个可能的疾病
        ],
        "rationale": runs[0].get("hypothesis", "Triage rationale.") if runs else "Triage rationale.",  # 推理依据
        "evidence": getattr(state, "retrieved_docs", [])  # 检索到的医疗文档证据
    }

    return state