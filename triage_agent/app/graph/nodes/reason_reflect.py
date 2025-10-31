import json
from app.observability.langsmith_tracer import trace_step
def reason_reflect(state):
    """
    Reason and reflect step:
    Based on retrieved documents, generate reasoning summary and reflection.
    """

    # 1️⃣ 安全读取输入
    patient_input = getattr(state, "patient_input", {}) or {}
    text = patient_input.get("text", "")
    retrieved_docs = getattr(state, "retrieved_docs", []) or []

    # 2️⃣ 遍历每个 RetrievalDoc 对象
    reasoning_summary = []
    for doc in retrieved_docs:
        # doc 是 RetrievalDoc 模型实例
        doc_text = getattr(doc, "text", "")
        score = getattr(doc, "score", 0)
        level = getattr(doc, "level", "unknown")

        if score > 0.8:
            reasoning_summary.append(
                f"[{level}] {doc_text} → suggests a possible high-risk or cardiac-related issue."
            )
        else:
            reasoning_summary.append(
                f"[{level}] {doc_text} → may be low priority or non-critical."
            )

    # 3️⃣ 总结输出
    reflection = {
        "reasoning": " ".join(reasoning_summary),
        "summary": f"Based on '{text}', possible cardiac concern detected; recommend further triage."
    }

    # 4️⃣ 更新状态
    state.reflection = reflection
    return state

    
