"""
Graph Service (graph_service.py)
================================
Neo4j 知识图谱服务 - 用于临床推理

提供基于 SNOMED CT 图谱的医学推理能力:
- 路径发现: 症状 → 潜在疾病
- 关系推理: 解剖部位、病理形态、因果关系
- 高危检测: 通过图遍历发现潜在风险

与 ESI Engine 配合使用，实现 "从匹配到推理" 的升级
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import os


@dataclass
class GraphContext:
    """图查询上下文 - 用于 ESI 评估"""
    concept_id: str
    concept_name: str
    finding_sites: List[Dict[str, str]] = field(default_factory=list)
    morphologies: List[Dict[str, str]] = field(default_factory=list)
    ancestors: List[Dict[str, str]] = field(default_factory=list)
    related_conditions: List[Dict[str, str]] = field(default_factory=list)
    related_procedures: List[Dict[str, str]] = field(default_factory=list)
    risk_paths: List[Dict[str, Any]] = field(default_factory=list)


class GraphService:
    """
    Neo4j 图服务

    提供面向临床推理的图查询接口
    """

    def __init__(self):
        """初始化图服务"""
        self._driver = None

    def _get_session(self):
        """获取 Neo4j session"""
        from data_pipeline.neo4j_db import neo4j_conn
        return neo4j_conn()

    def get_concept_context(self, sctid: str) -> GraphContext:
        """
        获取概念的完整图上下文

        包括: 解剖部位、病理形态、祖先类别、相关疾病和操作

        Args:
            sctid: SNOMED CT concept ID

        Returns:
            GraphContext 对象
        """
        context = GraphContext(concept_id=sctid, concept_name="")

        with self._get_session() as session:
            # 获取概念基本信息
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})
                RETURN c.FSN AS fsn
            """, sctid=sctid)
            record = result.single()
            if record:
                context.concept_name = record["fsn"]

            # 获取解剖部位 (FINDING_SITE)
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})-[:HAS_ROLE_GROUP]->(:RoleGroup)-[:FINDING_SITE]->(site:ObjectConcept)
                RETURN DISTINCT site.sctid AS sctid, site.FSN AS fsn
                LIMIT 10
            """, sctid=sctid)
            context.finding_sites = [
                {"sctid": r["sctid"], "fsn": r["fsn"]}
                for r in result
            ]

            # 获取病理形态 (ASSOCIATED_MORPHOLOGY)
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})-[:HAS_ROLE_GROUP]->(:RoleGroup)-[:ASSOCIATED_MORPHOLOGY]->(morph:ObjectConcept)
                RETURN DISTINCT morph.sctid AS sctid, morph.FSN AS fsn
                LIMIT 10
            """, sctid=sctid)
            context.morphologies = [
                {"sctid": r["sctid"], "fsn": r["fsn"]}
                for r in result
            ]

            # 获取祖先类别 (ISA 向上 3 层)
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})-[:ISA*1..3]->(ancestor:ObjectConcept)
                WHERE ancestor.active = '1'
                RETURN DISTINCT ancestor.sctid AS sctid, ancestor.FSN AS fsn
                LIMIT 20
            """, sctid=sctid)
            context.ancestors = [
                {"sctid": r["sctid"], "fsn": r["fsn"]}
                for r in result
            ]

        return context

    def find_risk_associations(
        self,
        sctid: str,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        发现潜在风险关联

        通过图遍历找到与输入症状相关的高危疾病

        Args:
            sctid: 症状的 SNOMED ID
            max_depth: 最大遍历深度

        Returns:
            风险关联列表
        """
        risk_associations = []

        # 高危疾病类别 SNOMED codes
        HIGH_RISK_CATEGORIES = [
            "22298006",   # Myocardial infarction
            "230690007",  # Stroke
            "233604007",  # Pneumonia
            "84114007",   # Heart failure
            "74400008",   # Appendicitis
            "85898001",   # Sepsis
            "59282003",   # Pulmonary embolism
        ]

        with self._get_session() as session:
            # 查找是否通过 ISA 关系连接到高危类别
            for risk_code in HIGH_RISK_CATEGORIES:
                result = session.run("""
                    MATCH path = (c:ObjectConcept {sctid: $sctid})-[:ISA*1..%d]->(risk:ObjectConcept {sctid: $risk_code})
                    RETURN risk.sctid AS risk_sctid, risk.FSN AS risk_name, length(path) AS distance
                    LIMIT 1
                """ % max_depth, sctid=sctid, risk_code=risk_code)

                record = result.single()
                if record:
                    risk_associations.append({
                        "risk_sctid": record["risk_sctid"],
                        "risk_name": record["risk_name"],
                        "distance": record["distance"],
                        "relationship": "ISA (是一种)"
                    })

            # 查找通过 FINDING_SITE 关联的高危情况
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})-[:HAS_ROLE_GROUP]->(:RoleGroup)-[:FINDING_SITE]->(site:ObjectConcept)
                WHERE site.sctid IN ['80891009', '12738006', '39607008']  // Heart, Brain, Lung
                RETURN site.sctid AS site_sctid, site.FSN AS site_name
            """, sctid=sctid)

            for record in result:
                risk_associations.append({
                    "risk_sctid": record["site_sctid"],
                    "risk_name": record["site_name"],
                    "distance": 1,
                    "relationship": "FINDING_SITE (发生部位)"
                })

        return risk_associations

    def get_differential_diagnoses(
        self,
        symptom_sctids: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取鉴别诊断

        基于多个症状找到可能的疾病

        Args:
            symptom_sctids: 症状 SNOMED ID 列表
            limit: 最大返回数量

        Returns:
            可能的疾病列表，按匹配度排序
        """
        differentials = []

        if not symptom_sctids:
            return differentials

        with self._get_session() as session:
            # 找到与这些症状共享关联的疾病
            result = session.run("""
                UNWIND $sctids AS symptom_id
                MATCH (symptom:ObjectConcept {sctid: symptom_id})<-[:ASSOCIATED_FINDING|CLINICAL_FINDING]-(disease:ObjectConcept)
                WHERE disease.active = '1'
                WITH disease, count(DISTINCT symptom_id) AS match_count
                RETURN disease.sctid AS sctid, disease.FSN AS fsn, match_count
                ORDER BY match_count DESC
                LIMIT $limit
            """, sctids=symptom_sctids, limit=limit)

            for record in result:
                differentials.append({
                    "sctid": record["sctid"],
                    "fsn": record["fsn"],
                    "match_count": record["match_count"],
                    "confidence": record["match_count"] / len(symptom_sctids)
                })

        return differentials

    def get_related_procedures(self, sctid: str) -> List[Dict[str, str]]:
        """
        获取相关检查/操作

        用于 ESI 资源评估

        Args:
            sctid: 症状或疾病的 SNOMED ID

        Returns:
            相关操作列表
        """
        procedures = []

        with self._get_session() as session:
            # 通过各种关系查找相关操作
            result = session.run("""
                MATCH (c:ObjectConcept {sctid: $sctid})-[r]->(proc:ObjectConcept)
                WHERE type(r) IN ['METHOD', 'PROCEDURE_SITE', 'INTERPRETS', 'HAS_SPECIMEN']
                AND proc.active = '1'
                RETURN DISTINCT proc.sctid AS sctid, proc.FSN AS fsn, type(r) AS rel_type
                LIMIT 10
            """, sctid=sctid)

            for record in result:
                procedures.append({
                    "sctid": record["sctid"],
                    "fsn": record["fsn"],
                    "relationship": record["rel_type"]
                })

        return procedures

    def check_red_flag_path(
        self,
        from_sctid: str,
        to_category: str
    ) -> Optional[Dict[str, Any]]:
        """
        检查是否存在到高危类别的路径

        Args:
            from_sctid: 起始概念 ID
            to_category: 目标高危类别 ID

        Returns:
            路径信息或 None
        """
        with self._get_session() as session:
            result = session.run("""
                MATCH path = shortestPath(
                    (start:ObjectConcept {sctid: $from_sctid})-[*1..5]-(end:ObjectConcept {sctid: $to_category})
                )
                RETURN length(path) AS distance,
                       [n IN nodes(path) | n.FSN] AS path_names
                LIMIT 1
            """, from_sctid=from_sctid, to_category=to_category)

            record = result.single()
            if record:
                return {
                    "distance": record["distance"],
                    "path": record["path_names"],
                    "from": from_sctid,
                    "to": to_category
                }

        return None

    def enrich_symptoms_with_graph(
        self,
        symptoms: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        使用图信息丰富症状数据

        为每个症状添加图上下文，供 ESI 引擎使用

        Args:
            symptoms: 症状列表

        Returns:
            增强后的症状列表
        """
        enriched = []

        for symptom in symptoms:
            sctid = symptom.get("sctid")
            if not sctid:
                enriched.append(symptom)
                continue

            # 获取图上下文
            context = self.get_concept_context(sctid)

            # 查找风险关联
            risks = self.find_risk_associations(sctid)

            # 获取相关操作
            procedures = self.get_related_procedures(sctid)

            # 构建增强后的症状
            enriched_symptom = {
                **symptom,
                "graph_context": {
                    "finding_sites": context.finding_sites,
                    "morphologies": context.morphologies,
                    "ancestors": context.ancestors,
                    "risk_associations": risks,
                    "related_procedures": procedures
                }
            }
            enriched.append(enriched_symptom)

        return enriched


# ========== 便捷函数 ==========

_graph_service = None


def get_graph_service() -> GraphService:
    """获取图服务单例"""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service


def enrich_with_graph(symptoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    便捷函数：用图信息丰富症状

    Example:
        >>> symptoms = [{"symptom": "chest pain", "sctid": "29857009"}]
        >>> enriched = enrich_with_graph(symptoms)
        >>> print(enriched[0]["graph_context"]["finding_sites"])
    """
    return get_graph_service().enrich_symptoms_with_graph(symptoms)


def find_risks(sctid: str) -> List[Dict[str, Any]]:
    """
    便捷函数：查找风险关联

    Example:
        >>> risks = find_risks("29857009")  # Chest pain
        >>> for r in risks:
        ...     print(f"{r['risk_name']} (distance: {r['distance']})")
    """
    return get_graph_service().find_risk_associations(sctid)


# ========== 测试代码 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("Graph Service Test")
    print("=" * 60)

    service = GraphService()

    # 测试: 胸痛的图上下文
    print("\n1. Testing concept context for 'Chest pain' (29857009):")
    context = service.get_concept_context("29857009")
    print(f"   Concept: {context.concept_name}")
    print(f"   Finding Sites: {len(context.finding_sites)}")
    for site in context.finding_sites[:3]:
        print(f"     - {site['fsn']}")
    print(f"   Morphologies: {len(context.morphologies)}")
    print(f"   Ancestors: {len(context.ancestors)}")
    for anc in context.ancestors[:3]:
        print(f"     - {anc['fsn']}")

    # 测试: 风险关联
    print("\n2. Testing risk associations:")
    risks = service.find_risk_associations("29857009")
    for risk in risks:
        print(f"   - {risk['risk_name']} via {risk['relationship']}")

    # 测试: 相关操作
    print("\n3. Testing related procedures:")
    procs = service.get_related_procedures("29857009")
    for proc in procs[:5]:
        print(f"   - {proc['fsn']} ({proc['relationship']})")
