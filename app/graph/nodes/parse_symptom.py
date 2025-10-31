from app.utils import snomed_lookup, icd_lookup
def parse_symptom(state: dict) -> dict:
    # 从 GraphState 中安全地取出输入文本
    patient_input = getattr(state, "patient_input", {}) or {}
    text = (patient_input.get("text", "") or "").lower()

    # 模拟实体提取逻辑（可替换为真实 NER 模型）
    entities = []
    if "chest" in text:
        entities.append({"symptom": "chest pain", "duration": None, "severity": "moderate"})
    if "breath" in text:
        entities.append({"symptom": "shortness of breath", "duration": None, "severity": "moderate"})

    # 返回更新的状态
    state.entities = entities
    return state
