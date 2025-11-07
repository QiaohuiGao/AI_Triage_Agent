"""
推理反思节点 (reason_reflect.py)
===============================
本节点负责基于检索到的医疗文档进行推理和反思。

功能：
- 分析检索到的医疗文档，生成推理摘要
- 评估文档的置信度和相关性
- 生成基于证据的推理结论和反思总结
- 识别高风险症状（如心脏相关疾病）

当前实现使用简单的规则，生产环境应使用：
- LLM（如 GPT-4, Claude）进行推理
- Chain-of-Thought 推理链
- 多文档证据聚合

输入：GraphState.retrieved_docs
输出：GraphState.reflection
"""

# import json
# from app.observability.langsmith_tracer import trace_step

# def reason_reflect(state):
#     """
#     推理反思节点
    
#     基于检索到的医疗文档，生成推理摘要和反思。
#     分析文档的置信度和相关性，识别高风险症状。
    
#     参数:
#         state: GraphState 对象，包含 retrieved_docs 字段
    
#     返回:
#         更新后的 GraphState，包含 reflection 字段
#     """
#     # ========== 读取输入 ==========
#     # 安全地从 GraphState 中读取输入数据
#     patient_input = getattr(state, "patient_input", {}) or {}
#     text = patient_input.get("text", "")                  # 患者症状描述
#     retrieved_docs = getattr(state, "retrieved_docs", []) or []  # 检索到的医疗文档

#     # ========== 文档分析 ==========
#     # 遍历每个检索到的文档，分析其内容和置信度
#     # 生产环境应使用 LLM 进行更复杂的推理
#     reasoning_summary = []
    
#     #这里怎么结合多个reasoning run 的结果

#     #这里又个大大的疑问，数据库直接存文档吗？
#     for doc in retrieved_docs:
#         # doc 是 RetrievalDoc 模型实例
#         # 安全地获取文档属性
#         doc_text = getattr(doc, "text", "")      # 文档文本
#         score = getattr(doc, "score", 0)          # 相似度得分
#         level = getattr(doc, "level", "unknown")   # 置信等级

#         # ========== 风险评估 ==========
#         # 根据文档的相似度得分判断风险等级
#         # 得分 > 0.8 表示高风险或心脏相关问题
#         # 得分 < 0.8 表示低优先级或非危急情况
#         if score > 0.8:
#             reasoning_summary.append(
#                 f"[{level}] {doc_text} → suggests a possible high-risk or cardiac-related issue."
#             )
#         else:
#             reasoning_summary.append(
#                 f"[{level}] {doc_text} → may be low priority or non-critical."
#             )

#     # ========== 生成反思总结 ==========
#     # 将推理摘要组合成完整的反思输出
#     # 生产环境应使用 LLM 生成更专业的医疗推理
#     reflection = {
#         "reasoning": " ".join(reasoning_summary),  # 推理摘要（所有文档的分析）
#         "summary": f"Based on '{text}', possible cardiac concern detected; recommend further triage."  # 总结
#     }

#     # ========== 更新状态 ==========
#     # 将反思结果添加到 GraphState 中
#     # 后续节点（VoteConfidence）会使用这些信息进行聚合
#     state.reflection = reflection
    
#     return state

# app/graph/nodes/reason_reflect.py
from app.schemas import GraphState
from openai import OpenAI
from loguru import logger
import os

# 读取环境变量
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 系统提示词：告诉模型角色和任务范围
SYSTEM_PROMPT = """
You are a clinical triage assistant specializing in Traumatic Brain Injury (TBI).
Base your reasoning STRICTLY on the provided evidence.

For each conclusion, include:
- Reasoning (why)
- Evidence citation (title or guideline source)
- Risk level (low / medium / high)
- Recommendation (next clinical action)

If evidence is insufficient, say clearly:
"Insufficient evidence — recommend in-person evaluation."
"""

def reason_reflect(state: GraphState) -> GraphState:
    docs = state.retrieved_docs or []
    query = state.patient_input.get("text", "") if state.patient_input else ""

    # ✅ 1. 如果没有检索到任何文档，提前返回
    if not docs:
        logger.warning("⚠️ 没有检索到任何证据文档")
        state.reflection = {
            "summary": "未检索到相关医学证据，建议人工复核。",
            "model": "none",
            "num_evidence": 0
        }
        return state

    # ✅ 2. 构造 LLM 推理输入（将所有文档合并为上下文）
    context = "\n\n".join([f"({i+1}) [{d.source}] {d.text}" for i, d in enumerate(docs)])

    # ✅ 3. 组合提示词
    user_prompt = f"""
User input:
{query}

Evidence base:
{context}

Answer:
"""

    # ✅ 4. 调用 OpenAI 进行推理
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        output = resp.choices[0].message.content

        # ✅ 5. 将推理结果写入 GraphState.reflection
        state.reflection = {
            "summary": output,
            "model": "gpt-4o-mini",
            "num_evidence": len(docs),
        }

        logger.info("✅ 推理反思节点执行成功")

    except Exception as e:
        # ✅ 6. 捕获错误，避免 500 错误中断整个流程
        logger.error(f"❌ LLM 推理失败: {e}")
        state.reflection = {
            "summary": f"推理失败，错误信息: {e}",
            "model": "error",
            "num_evidence": len(docs),
        }

    return state