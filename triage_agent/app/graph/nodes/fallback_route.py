from app.config import AGREEMENT_MIN, CONFIDENCE_MIN, RED_FLAG_TERMS
from app.schemas import GraphState  # 导入 GraphState 类型

ROUTING_TABLE = {
    "Angina": ("Cardiology", "Urgent"),
    "Pulmonary embolism": ("Emergency", "ER"),
    "Muscle strain": ("Orthopedics", "Routine"),
    "Undifferentiated complaint": ("Primary Care", "Routine")
}

def fallback_route(state: GraphState) -> GraphState:
    """
    Fallback logic for triage routing if confidence or agreement is low.
    Compatible with Pydantic GraphState.
    """
    # ✅ 取输入文本
    patient_input = getattr(state, "patient_input", {}) or {}
    text = patient_input.get("text", "").lower()

    # ✅ 取 voting 结果
    vote = getattr(state, "voting_result", None)
    if not vote:
        vote = {"avg_confidence": 0.0, "agreement": 0.0}
    avg_conf = vote.get("avg_confidence", 0.0)
    agreement = vote.get("agreement", 0.0)

    # ✅ 取 reasoning_runs
    runs = getattr(state, "reasoning_runs", []) or []
    conds = []
    if runs and isinstance(runs[0], dict):
        conds = runs[0].get("conditions", [])
    conds = conds or ["Undifferentiated complaint"]

    # ✅ Red flag rule
    if any(t in text for t in RED_FLAG_TERMS):
        state.final_output = {
            "suggested_department": "Emergency",
            "urgency": "ER",
            "confidence": 0.99,
            "agreement": agreement,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": "Red-flag safety rule triggered.",
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ✅ 低置信度 / 低一致性 → Primary Care
    if avg_conf < CONFIDENCE_MIN or agreement < AGREEMENT_MIN:
        state.final_output = {
            "suggested_department": "Primary Care",
            "urgency": "Routine",
            "confidence": avg_conf,
            "agreement": agreement,
            "final_conditions": [{"condition": conds[0], "confidence": avg_conf}],
            "rationale": "Conservative routing due to low confidence/agreement.",
            "evidence": getattr(state, "retrieved_docs", [])
        }
        return state

    # ✅ 正常 routing
    dept, urg = ROUTING_TABLE.get(conds[0], ("Primary Care", "Routine"))
    state.final_output = {
        "suggested_department": dept,
        "urgency": urg,
        "confidence": avg_conf,
        "agreement": agreement,
        "final_conditions": [
            {"condition": c, "confidence": avg_conf} for c in conds[:3]
        ],
        "rationale": runs[0].get("hypothesis", "Triage rationale.") if runs else "Triage rationale.",
        "evidence": getattr(state, "retrieved_docs", [])
    }

    return state