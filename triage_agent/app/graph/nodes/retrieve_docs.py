from app.retriever.llama_index_retriever import retrieve_multi
import uuid
import random

def retrieve_docs(state):
    """
    根据症状实体从向量数据库中检索相关文档。
    """

    # ✅ 安全获取实体列表
    entities = getattr(state, "entities", []) or []

    # ✅ 模拟从 Pinecone / LlamaIndex 检索的结果
    retrieved = []
    for e in entities:
        symptom = e.get("symptom", "")

        # 生成两条 mock 检索结果
        for i, doc_text in enumerate([
            f"Clinical guideline for {symptom}",
            f"Possible causes and treatment for {symptom}"
        ]):
            retrieved.append({
                "id": str(uuid.uuid4()),           # 唯一标识符
                "text": doc_text,                  # 文档内容
                "score": round(random.uniform(0.7, 0.99), 2),  # 相似度得分
                "level": "high" if i == 0 else "medium",       # 置信等级
                "source": "mock_db",               # 来源标识（Pinecone/LlamaIndex）
            })

    # ✅ 更新 GraphState
    state.retrieved_docs = retrieved
    return state
