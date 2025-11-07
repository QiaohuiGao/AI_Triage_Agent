"""
症状解析节点 (parse_symptom.py)
===============================
本节点负责从患者描述中提取症状实体。

功能：
- 从患者输入文本中提取症状关键词
- 识别症状的类型、持续时间和严重程度
- 将提取的实体添加到 GraphState.entities 中

当前实现使用简单的关键词匹配，生产环境应替换为：
- 专业的 NER（命名实体识别）模型
- 医疗知识图谱实体链接
- SNOMED CT / ICD-10 编码映射

输入：GraphState.patient_input
输出：GraphState.entities
"""

from app.utils import snomed_lookup, icd_lookup

def parse_symptom(state: dict) -> dict:
    """
    解析症状节点
    
    从患者描述中提取症状实体，包括：
    - 症状名称（如 "chest pain", "shortness of breath"）
    - 持续时间（可扩展）
    - 严重程度（可扩展）
    
    参数:
        state: GraphState 对象，包含 patient_input
    
    返回:
        更新后的 GraphState，包含 entities 字段
    """
    # ========== 提取输入文本 ==========
    # 从 GraphState 中安全地取出输入文本
    # 使用 getattr 和默认值确保健壮性
    #这里考虑语音转化文字后的输入
    patient_input = getattr(state, "patient_input", {}) or {}
    text = (patient_input.get("text", "") or "").lower()  # 转换为小写以便匹配

    # ========== 实体提取逻辑 ==========
    # 模拟实体提取逻辑（可替换为真实 NER 模型）
    # 生产环境应使用：
    # - spaCy 医疗 NER 模型
    # - BERT-based 医疗实体识别
    # - 医疗知识图谱实体链接
    # 实践以上其中一个拓展方案，加入一个可靠的医疗模型，存入数据库，或者存入知识图谱？
    entities = []
    
    # 简单的关键词匹配示例
    # 拓展成一种retrieve策略，怎么样去将收到结构化输入，去和数据库里面的症状进行匹配？有没有可用的线上诊断模型可以借鉴？
    #不对，这里的核心输出还是一个结构化的entity，就是将人数的话，转化成结构化的输入，通过将他本体话otology mapping with professional term.
    #"头有点晕"->"眩晕，轻微"
    if "chest" in text:
        entities.append({
            "symptom": "chest pain",      # 症状名称
            "duration": None,              # 持续时间（待扩展）
            "severity": "moderate"         # 严重程度（待扩展）
        })
    if "breath" in text:
        entities.append({
            "symptom": "shortness of breath",  # 症状名称
            "duration": None,                  # 持续时间（待扩展）
            "severity": "moderate"             # 严重程度（待扩展）
        })

    # ========== 更新状态 ==========
    # 将提取的实体添加到 GraphState 中
    # 后续节点（RetrieveDocs）会使用这些实体进行文档检索
    state.entities = entities
    
    return state
