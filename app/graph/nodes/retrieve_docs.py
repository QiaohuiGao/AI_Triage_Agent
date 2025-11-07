# """
# 文档检索节点 (retrieve_docs.py)
# ===============================
# 本节点负责从向量数据库中检索与症状相关的医疗文档。

# 功能：
# - 根据提取的症状实体，从 Pinecone 向量数据库检索相关文档
# - 检索来自三个索引：症状索引、疾病索引、诊疗路径索引
# - 返回文档的相似度得分、置信等级和来源信息

# 当前实现使用模拟数据，生产环境应使用：
# - LlamaIndex 向量检索器
# - Pinecone 向量数据库
# - 医疗知识库（临床指南、疾病数据库、诊疗路径）

# 输入：GraphState.entities
# 输出：GraphState.retrieved_docs
# """

# from app.retriever.llama_index_retriever import retrieve_multi
# import uuid
# import random

# def retrieve_docs(state):
#     """
#     文档检索节点
    
#     根据症状实体从向量数据库中检索相关医疗文档。
#     检索的文档包括：
#     - 临床指南（症状处理指南）
#     - 疾病诊断信息（可能的疾病）
#     - 诊疗路径（科室推荐路径）
    
#     参数:
#         state: GraphState 对象，包含 entities 字段
    
#     返回:
#         更新后的 GraphState，包含 retrieved_docs 字段
#     """
#     # ========== 获取症状实体 ==========
#     # 从 GraphState 中安全地获取实体列表
#     # 这些实体由 ParseSymptom 节点填充
#     entities = getattr(state, "entities", []) or []

#     # ========== 向量检索 ==========
#     # 模拟从 Pinecone / LlamaIndex 检索的结果
#     # 生产环境应调用：
#     #   retrieved_docs = retrieve_multi(query_text, k=5)
#     # 其中 query_text 是从 entities 构建的查询文本

#     # 拓展成一种retrieve策略，怎么样去将收到结构化输入(entity)，去和数据库里面的症状进行匹配？有没有可用的症状entity->疾病判断模型可以借鉴?

#     retrieved = []
    
#     # 遍历每个症状实体，检索相关文档
#     for e in entities:
#         symptom = e.get("symptom", "")

#         # ========== 生成检索结果 ==========
#         # 为每个症状生成两条 mock 检索结果
#         # 生产环境应使用真实的向量检索，返回：
#         # - 临床指南文档
#         # - 疾病诊断文档
#         # - 诊疗路径文档
#         for i, doc_text in enumerate([
#             f"Clinical guideline for {symptom}",           # 临床指南
#             f"Possible causes and treatment for {symptom}"  # 可能的原因和治疗
#         ]):
#             retrieved.append({
#                 "id": str(uuid.uuid4()),           # 文档唯一标识符
#                 "text": doc_text,                  # 文档文本内容
#                 "score": round(random.uniform(0.7, 0.99), 2),  # 相似度得分（0-1），这里的相似度得分是不是也太鲁莽了？
#                 "level": "high" if i == 0 else "medium",       # 置信等级：high/medium/low
#                 "source": "mock_db",               # 来源标识（Pinecone/LlamaIndex）
#             })

#     # ========== 更新状态 ==========
#     # 将检索到的文档添加到 GraphState 中
#     # 后续节点（ReasonReflect）会使用这些文档进行推理
#     state.retrieved_docs = retrieved
    
#     return state



# app/graph/nodes/retrieve_docs.py
# app/graph/nodes/retrieve_docs.py
from typing import Dict, Any
from loguru import logger

from app.schemas import GraphState, RetrievedDoc
from app.retriever.HybridRetriever import HybridRetriever


# 单例 retriever，避免重复加载 FAISS
_retriever = None


def _get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
        logger.info("🔍 HybridRetriever initialized.")
    return _retriever


def retrieve_docs(state: GraphState) -> Dict[str, Any]:
    """
    检索节点：从 PostgreSQL + FAISS 混合索引中检索相关医学指南
    输入：GraphState.text / input_text
    输出：{ "retrieved_docs": [RetrievedDoc, ...] }
    """
    # ✅ 从 GraphState.patient_input 中获取用户文本
    query = None
    if state.patient_input and isinstance(state.patient_input, dict):
        query = state.patient_input.get("text", None)

    if not query:
        logger.warning("⚠️ retrieve_docs: empty query")
        return {"retrieved_docs": []}  # ✅ 必须返回合法字段

    filters = {"tags": ["tbi"]}

    retriever = _get_retriever()
    docs = retriever.search(query=query, topk=8, filters=filters, use_faiss=True, use_bm25=True)

    if not docs:
        logger.warning("⚠️ retrieve_docs: no docs found for query")
        return {"retrieved_docs": []}

    logger.info(f"✅ Retrieved {len(docs)} docs for query: {query}")

    # ✅ 转换为 RetrievedDoc 列表（符合 GraphState 定义）
    retrieved_docs = [
        RetrievedDoc(
            level="condition",  # 或 symptom/path，根据数据结构修改
            id=str(d["id"]),
            score=float(d.get("score", 0.0)),
            text=d.get("text", ""),
            source=d.get("source", "hybrid_retriever")
        )
        for d in docs
    ]

    return {"retrieved_docs": retrieved_docs}