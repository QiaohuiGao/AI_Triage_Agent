"""
症状解析节点 (parse_symptom.py)
===============================
本节点负责从患者描述中提取症状实体。

功能：
- 从患者输入文本中提取症状关键词
- 识别症状的类型、持续时间和严重程度
- 将提取的实体添加到 GraphState.entities 中
- 使用 Neo4j SNOMED CT 知识图谱进行术语标准化

数据源：
- Neo4j: SNOMED CT 知识图谱 (主要来源，包含层级关系)
- PostgreSQL: snomed_descriptions 表 (备用)

输入：GraphState.patient_input
输出：GraphState.entities
"""

import re
import os
from typing import List, Dict, Any, Optional
from app.schemas import GraphState

# Flag to control which backend to use
USE_NEO4J = os.getenv("USE_NEO4J_SNOMED", "true").lower() == "true"


def snomed_match_neo4j(symptom_text: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    在 Neo4j SNOMED CT 知识图谱中查找匹配项

    Args:
        symptom_text: 症状文本
        limit: 最大返回数量

    Returns:
        匹配的 SNOMED CT 概念列表，包含 sctid, fsn, 和层级信息
    """
    try:
        from data_pipeline.neo4j_db import neo4j_conn

        # Search in Description nodes for more comprehensive matching
        query = """
        MATCH (d:Description)
        WHERE toLower(d.term) CONTAINS toLower($term)
        AND d.active = '1'
        WITH d
        MATCH (c:ObjectConcept {sctid: d.sctid})
        WHERE c.active = '1'
        RETURN DISTINCT
            c.sctid AS sctid,
            c.FSN AS fsn,
            d.term AS matched_term
        ORDER BY
            CASE WHEN toLower(d.term) = toLower($term) THEN 0 ELSE 1 END,
            size(d.term)
        LIMIT $limit
        """

        with neo4j_conn() as session:
            result = session.run(query, term=symptom_text, limit=limit)
            matches = []
            for record in result:
                matches.append({
                    "sctid": record["sctid"],
                    "fsn": record["fsn"],
                    "matched_term": record["matched_term"]
                })
            return matches
    except Exception as e:
        print(f"Neo4j SNOMED lookup failed: {e}")
        return []


def snomed_get_hierarchy(sctid: str, depth: int = 3) -> Dict[str, Any]:
    """
    获取 SNOMED CT 概念的层级信息（父级和子级）

    Args:
        sctid: SNOMED CT 概念 ID
        depth: 向上查找的层级数

    Returns:
        包含 parents 和 children 的层级信息
    """
    try:
        from data_pipeline.neo4j_db import neo4j_conn, snomed_get_parents, snomed_get_children

        parents = snomed_get_parents(sctid, limit=5)
        children = snomed_get_children(sctid, limit=5)

        return {
            "parents": parents,
            "children": children
        }
    except Exception as e:
        print(f"Neo4j hierarchy lookup failed: {e}")
        return {"parents": [], "children": []}


def snomed_match_postgres(symptom_text: str, limit: int = 5) -> List[tuple]:
    """
    在 PostgreSQL SNOMED 术语表中查找匹配项 (备用方案)

    Args:
        symptom_text: 症状文本
        limit: 最大返回数量

    Returns:
        匹配的 (conceptId, term) 元组列表
    """
    try:
        from data_pipeline.common_db import pg_conn

        with pg_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT conceptId, term FROM snomed_descriptions
                WHERE term ILIKE %s AND active = TRUE
                LIMIT %s
            """, (f"%{symptom_text}%", limit))
            return cur.fetchall()
    except Exception as e:
        print(f"PostgreSQL SNOMED lookup failed: {e}")
        return []


def snomed_match(symptom_text: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    统一的 SNOMED CT 查找接口
    优先使用 Neo4j，如果失败则回退到 PostgreSQL

    Args:
        symptom_text: 症状文本
        limit: 最大返回数量

    Returns:
        匹配的 SNOMED CT 概念列表
    """
    if USE_NEO4J:
        matches = snomed_match_neo4j(symptom_text, limit)
        if matches:
            return matches

    # Fallback to PostgreSQL
    pg_matches = snomed_match_postgres(symptom_text, limit)
    return [
        {"sctid": str(m[0]), "fsn": m[1], "matched_term": m[1]}
        for m in pg_matches
    ]


def extract_severity(text: str, symptom: str) -> str:
    """
    从文本中提取症状的严重程度

    Args:
        text: 完整的患者描述文本
        symptom: 已识别的症状

    Returns:
        严重程度: "severe", "moderate", "mild", 或数字评分
    """
    text_lower = text.lower()

    # 严重程度指示词
    severe_indicators = [
        "severe", "worst", "terrible", "excruciating", "unbearable",
        "extreme", "intense", "very bad", "awful", "agonizing",
        "sudden", "thunderclap", "crushing", "stabbing",
        "10/10", "10 out of 10", "9/10", "9 out of 10", "8/10", "8 out of 10",
        "can't bear", "worst ever", "worst of my life"
    ]

    moderate_indicators = [
        "moderate", "significant", "noticeable", "considerable",
        "7/10", "7 out of 10", "6/10", "6 out of 10", "5/10", "5 out of 10"
    ]

    mild_indicators = [
        "mild", "slight", "minor", "little", "small", "light",
        "not too bad", "manageable", "tolerable",
        "1/10", "1 out of 10", "2/10", "2 out of 10", "3/10", "3 out of 10",
        "4/10", "4 out of 10"
    ]

    # 检查数字评分模式 (e.g., "pain is 8 out of 10")
    pain_scale_match = re.search(r'(\d+)\s*(?:out\s*of\s*10|/10)', text_lower)
    if pain_scale_match:
        score = int(pain_scale_match.group(1))
        if score >= 8:
            return "severe"
        elif score >= 5:
            return "moderate"
        else:
            return "mild"

    # 检查严重程度修饰词是否出现在症状附近
    symptom_lower = symptom.lower()
    # 找到症状在文本中的位置
    symptom_pos = text_lower.find(symptom_lower)
    if symptom_pos == -1:
        # 如果找不到完全匹配，尝试部分匹配
        for part in symptom_lower.split():
            if part in text_lower:
                symptom_pos = text_lower.find(part)
                break

    # 检查症状前后的上下文（前后50个字符）
    context_start = max(0, symptom_pos - 50) if symptom_pos != -1 else 0
    context_end = min(len(text_lower), symptom_pos + len(symptom_lower) + 50) if symptom_pos != -1 else len(text_lower)
    context = text_lower[context_start:context_end]

    # 按优先级检查
    for indicator in severe_indicators:
        if indicator in context or indicator in text_lower:
            return "severe"

    for indicator in moderate_indicators:
        if indicator in context or indicator in text_lower:
            return "moderate"

    for indicator in mild_indicators:
        if indicator in context or indicator in text_lower:
            return "mild"

    # 默认为 moderate
    return "moderate"


def extract_symptom_keywords(text: str) -> List[str]:
    """
    从文本中提取潜在的症状关键词

    使用多种策略：
    1. 预定义的医学术语正则表达式
    2. 常见症状词汇表
    3. 名词短语提取（可扩展为 NER）

    Args:
        text: 患者描述文本

    Returns:
        提取的关键词列表
    """
    # 常见症状关键词模式
    symptom_patterns = [
        # 疼痛相关
        r"\b(headache|chest\s*pain|back\s*pain|abdominal\s*pain|pain)\b",
        # 神经系统
        r"\b(dizziness|vertigo|unconscious|confusion|memory\s*loss|seizure)\b",
        # 呼吸系统
        r"\b(cough|shortness\s*of\s*breath|breathing\s*difficulty|wheezing)\b",
        # 消化系统
        r"\b(nausea|vomiting|diarrhea|constipation)\b",
        # 全身症状
        r"\b(fever|fatigue|weakness|sweating|chills)\b",
        # 心血管
        r"\b(palpitation|chest\s*tightness|fainting)\b",
        # 外伤
        r"\b(injury|trauma|wound|fracture|bleeding)\b",
        # 其他常见
        r"\b(rash|swelling|numbness|tingling)\b",
    ]

    candidates = []
    text_lower = text.lower()

    for pattern in symptom_patterns:
        matches = re.findall(pattern, text_lower, flags=re.I)
        candidates.extend(matches)

    # 去重并保持顺序
    seen = set()
    unique_candidates = []
    for c in candidates:
        c_normalized = c.lower().strip()
        if c_normalized not in seen:
            seen.add(c_normalized)
            unique_candidates.append(c)

    return unique_candidates


def parse_symptom(state: GraphState) -> GraphState:
    """
    解析症状节点 - 主入口函数

    从患者描述中提取症状实体，并通过 SNOMED CT 进行标准化

    Args:
        state: GraphState 对象，包含 patient_input

    Returns:
        更新后的 GraphState，包含 entities 字段
    """
    text = state.patient_input.get("text", "")

    # 提取症状关键词
    candidates = extract_symptom_keywords(text)

    # 如果没有提取到关键词，尝试更宽松的匹配
    if not candidates:
        # 使用原来的简单匹配作为后备
        candidates = re.findall(
            r"\b(headache|vomiting|unconscious|CT|injury|memory|pain|fever|cough)\b",
            text,
            flags=re.I
        )

    entities = []
    for symptom_text in candidates:
        # 在 SNOMED CT 中查找匹配
        snomed_matches = snomed_match(symptom_text)

        # 提取严重程度 (v2.0)
        severity = extract_severity(text, symptom_text)

        entity = {
            "symptom": symptom_text,
            "snomed_matches": snomed_matches,
            "sctid": snomed_matches[0]["sctid"] if snomed_matches else None,
            "fsn": snomed_matches[0]["fsn"] if snomed_matches else None,
            "severity": severity,  # v2.0: 添加严重程度
        }

        # 如果找到匹配，获取层级信息
        if snomed_matches and USE_NEO4J:
            try:
                hierarchy = snomed_get_hierarchy(snomed_matches[0]["sctid"])
                entity["hierarchy"] = hierarchy
            except Exception:
                pass

        entities.append(entity)

    state.entities = entities
    return state


# ========== 测试代码 ==========
if __name__ == "__main__":
    # 测试 SNOMED CT 查找
    print("Testing SNOMED CT lookup...")

    test_symptoms = ["headache", "chest pain", "fever", "cough"]

    for symptom in test_symptoms:
        print(f"\n--- Searching for: {symptom} ---")
        matches = snomed_match(symptom, limit=3)
        for m in matches:
            print(f"  [{m.get('sctid', 'N/A')}] {m.get('fsn', m.get('matched_term', 'N/A'))}")
