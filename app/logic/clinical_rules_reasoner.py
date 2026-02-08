"""
Clinical Rules Reasoner (clinical_rules_reasoner.py)
=====================================================

基于Neo4j临床决策规则的确定性推理引擎。

功能:
- 查询匹配的临床决策规则
- 计算规则覆盖度
- 生成针对性追问
- 提供evidence-based推荐
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class RuleMatch:
    """规则匹配结果"""
    rule_id: str
    rule_name: str
    risk_level: str
    guideline_source: str
    matched_criteria: List[str]
    missing_criteria: List[str]
    coverage: float  # 匹配的criteria / 总criteria
    action: Dict[str, Any]
    evidence_text: str


@dataclass
class ReasoningResult:
    """推理结果"""
    matched_rules: List[RuleMatch]
    highest_risk: str
    recommended_actions: List[Dict[str, Any]]
    clarifying_questions: List[Dict[str, Any]]
    reasoning_trace: List[str]
    confidence: float


class ClinicalRulesReasoner:
    """
    临床规则推理器

    使用Neo4j中的ClinicalRule节点进行确定性推理
    """

    def __init__(self):
        self._driver = None

    def _get_session(self):
        """获取Neo4j session"""
        try:
            from data_pipeline.neo4j_db import neo4j_conn
        except ModuleNotFoundError:
            from neo4j_db import neo4j_conn
        return neo4j_conn()

    def reason(
        self,
        symptom_sctids: List[str],
        symptom_keywords: List[str] = None,
        severity: str = "moderate"
    ) -> ReasoningResult:
        """
        基于症状进行规则匹配推理

        Args:
            symptom_sctids: 症状的SNOMED CT codes
            symptom_keywords: 症状关键词 (用于keyword匹配)
            severity: 严重程度

        Returns:
            ReasoningResult 推理结果
        """
        matched_rules = []
        reasoning_trace = []

        with self._get_session() as session:
            # 1. 通过SNOMED code查找匹配的规则
            snomed_matches = self._find_rules_by_snomed(session, symptom_sctids)
            matched_rules.extend(snomed_matches)
            reasoning_trace.append(f"SNOMED匹配: 找到{len(snomed_matches)}条规则")

            # 2. 通过关键词查找匹配的规则
            if symptom_keywords:
                keyword_matches = self._find_rules_by_keywords(session, symptom_keywords)
                # 去重
                existing_ids = {r.rule_id for r in matched_rules}
                for km in keyword_matches:
                    if km.rule_id not in existing_ids:
                        matched_rules.append(km)
                reasoning_trace.append(f"关键词匹配: 找到{len(keyword_matches)}条规则")

            # 3. 获取追问问题
            questions = self._get_clarifying_questions(session, matched_rules)

            # 4. 计算最高风险等级
            highest_risk = self._calculate_highest_risk(matched_rules, severity)

            # 5. 汇总推荐动作
            actions = self._aggregate_actions(matched_rules)

        # 计算置信度
        confidence = self._calculate_confidence(matched_rules)

        return ReasoningResult(
            matched_rules=matched_rules,
            highest_risk=highest_risk,
            recommended_actions=actions,
            clarifying_questions=questions,
            reasoning_trace=reasoning_trace,
            confidence=confidence
        )

    def _find_rules_by_snomed(
        self,
        session,
        sctids: List[str]
    ) -> List[RuleMatch]:
        """通过SNOMED code查找规则"""
        if not sctids:
            return []

        query = """
        UNWIND $sctids AS sctid
        MATCH (concept:ObjectConcept {sctid: sctid})<-[:MAPS_TO]-(criterion:Criterion)-[:TRIGGERS]->(rule:ClinicalRule)
        OPTIONAL MATCH (rule)-[:RECOMMENDS]->(action:Action)
        WITH rule, action, collect(DISTINCT criterion.criterion_id) as matched_criteria
        MATCH (all_criteria:Criterion)-[:TRIGGERS]->(rule)
        WITH rule, action, matched_criteria, collect(DISTINCT all_criteria.criterion_id) as all_criteria
        RETURN
            rule.rule_id as rule_id,
            rule.name as rule_name,
            rule.risk_level as risk_level,
            rule.guideline_source as guideline_source,
            rule.evidence_text as evidence_text,
            matched_criteria,
            all_criteria,
            action.type as action_type,
            action.urgency as action_urgency,
            action.rationale as action_rationale,
            action.tests as action_tests,
            action.procedure as action_procedure
        """

        results = []
        try:
            result = session.run(query, sctids=sctids)
            for record in result:
                matched = set(record["matched_criteria"])
                all_crit = set(record["all_criteria"])
                missing = all_crit - matched

                coverage = len(matched) / len(all_crit) if all_crit else 0

                results.append(RuleMatch(
                    rule_id=record["rule_id"],
                    rule_name=record["rule_name"],
                    risk_level=record["risk_level"] or "MEDIUM",
                    guideline_source=record["guideline_source"] or "",
                    matched_criteria=list(matched),
                    missing_criteria=list(missing),
                    coverage=coverage,
                    action={
                        "type": record["action_type"],
                        "urgency": record["action_urgency"],
                        "rationale": record["action_rationale"],
                        "tests": record["action_tests"] or [],
                        "procedure": record["action_procedure"],
                    },
                    evidence_text=record["evidence_text"] or ""
                ))
        except Exception as e:
            print(f"SNOMED rule query error: {e}")

        return results

    def _find_rules_by_keywords(
        self,
        session,
        keywords: List[str]
    ) -> List[RuleMatch]:
        """通过关键词查找规则"""
        if not keywords:
            return []

        # 构建关键词搜索查询
        query = """
        MATCH (criterion:Criterion)-[:TRIGGERS]->(rule:ClinicalRule)
        WHERE any(kw IN $keywords WHERE
            any(ckw IN criterion.keywords WHERE toLower(ckw) CONTAINS toLower(kw))
        )
        OPTIONAL MATCH (rule)-[:RECOMMENDS]->(action:Action)
        WITH rule, action, collect(DISTINCT criterion.criterion_id) as matched_criteria
        MATCH (all_criteria:Criterion)-[:TRIGGERS]->(rule)
        WITH rule, action, matched_criteria, collect(DISTINCT all_criteria.criterion_id) as all_criteria
        RETURN
            rule.rule_id as rule_id,
            rule.name as rule_name,
            rule.risk_level as risk_level,
            rule.guideline_source as guideline_source,
            rule.evidence_text as evidence_text,
            matched_criteria,
            all_criteria,
            action.type as action_type,
            action.urgency as action_urgency,
            action.rationale as action_rationale,
            action.tests as action_tests,
            action.procedure as action_procedure
        """

        results = []
        try:
            result = session.run(query, keywords=keywords)
            for record in result:
                matched = set(record["matched_criteria"])
                all_crit = set(record["all_criteria"])
                missing = all_crit - matched

                coverage = len(matched) / len(all_crit) if all_crit else 0

                results.append(RuleMatch(
                    rule_id=record["rule_id"],
                    rule_name=record["rule_name"],
                    risk_level=record["risk_level"] or "MEDIUM",
                    guideline_source=record["guideline_source"] or "",
                    matched_criteria=list(matched),
                    missing_criteria=list(missing),
                    coverage=coverage,
                    action={
                        "type": record["action_type"],
                        "urgency": record["action_urgency"],
                        "rationale": record["action_rationale"],
                        "tests": record["action_tests"] or [],
                        "procedure": record["action_procedure"],
                    },
                    evidence_text=record["evidence_text"] or ""
                ))
        except Exception as e:
            print(f"Keyword rule query error: {e}")

        return results

    def _get_clarifying_questions(
        self,
        session,
        matched_rules: List[RuleMatch]
    ) -> List[Dict[str, Any]]:
        """获取针对缺失条件的追问问题"""
        questions = []

        # 收集所有缺失的criteria
        missing_criteria_ids = set()
        for rule in matched_rules:
            missing_criteria_ids.update(rule.missing_criteria)

        if not missing_criteria_ids:
            return questions

        query = """
        MATCH (q:ClarifyingQuestion)-[:ASKS_ABOUT]->(c:Criterion)
        WHERE c.criterion_id IN $criteria_ids
        RETURN
            q.question_id as question_id,
            q.question as question,
            q.question_zh as question_zh,
            q.priority as priority,
            q.response_type as response_type,
            c.criterion_id as target_criterion
        ORDER BY q.priority
        LIMIT 5
        """

        try:
            result = session.run(query, criteria_ids=list(missing_criteria_ids))
            for record in result:
                questions.append({
                    "question_id": record["question_id"],
                    "question": record["question"],
                    "question_zh": record["question_zh"],
                    "priority": record["priority"],
                    "response_type": record["response_type"],
                    "target_criterion": record["target_criterion"],
                })
        except Exception as e:
            print(f"Question query error: {e}")

        return questions

    def _calculate_highest_risk(
        self,
        matched_rules: List[RuleMatch],
        severity: str
    ) -> str:
        """计算最高风险等级"""
        risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        highest = "LOW"
        for rule in matched_rules:
            if rule.coverage >= 0.5:  # 至少50%匹配才计入
                level = rule.risk_level
                if risk_order.get(level, 3) < risk_order.get(highest, 3):
                    highest = level

        # 严重程度调整
        if severity == "severe" and highest == "MEDIUM":
            highest = "HIGH"

        return highest

    def _aggregate_actions(
        self,
        matched_rules: List[RuleMatch]
    ) -> List[Dict[str, Any]]:
        """汇总推荐动作"""
        actions = []
        seen_types = set()

        # 按urgency排序
        urgency_order = {"IMMEDIATE": 0, "URGENT": 1, "ROUTINE": 2}
        sorted_rules = sorted(
            matched_rules,
            key=lambda r: urgency_order.get(r.action.get("urgency", "ROUTINE"), 2)
        )

        for rule in sorted_rules:
            action = rule.action
            if action.get("type") and action["type"] not in seen_types:
                seen_types.add(action["type"])
                actions.append({
                    "type": action["type"],
                    "urgency": action.get("urgency", "ROUTINE"),
                    "rationale": action.get("rationale", ""),
                    "tests": action.get("tests", []),
                    "procedure": action.get("procedure", ""),
                    "source_rule": rule.rule_id,
                    "guideline": rule.guideline_source,
                })

        return actions

    def _calculate_confidence(self, matched_rules: List[RuleMatch]) -> float:
        """计算推理置信度"""
        if not matched_rules:
            return 0.3  # 无匹配规则

        # 基于最高覆盖度和规则数量计算
        max_coverage = max(r.coverage for r in matched_rules)
        rule_count = len(matched_rules)

        confidence = max_coverage * 0.7 + min(rule_count / 5, 1.0) * 0.3

        return min(confidence, 1.0)

    def get_rule_details(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取规则详细信息"""
        with self._get_session() as session:
            query = """
            MATCH (rule:ClinicalRule {rule_id: $rule_id})
            OPTIONAL MATCH (rule)-[:RECOMMENDS]->(action:Action)
            OPTIONAL MATCH (criterion:Criterion)-[:TRIGGERS]->(rule)
            OPTIONAL MATCH (rule)-[:DEFINED_IN]->(guideline:Guideline)
            RETURN
                rule.rule_id as rule_id,
                rule.name as rule_name,
                rule.risk_level as risk_level,
                rule.description as description,
                rule.evidence_text as evidence_text,
                guideline.source as guideline_source,
                guideline.url as guideline_url,
                collect(DISTINCT {
                    id: criterion.criterion_id,
                    name: criterion.name,
                    type: criterion.type,
                    threshold: criterion.threshold
                }) as criteria,
                action.type as action_type,
                action.urgency as action_urgency,
                action.rationale as action_rationale
            """

            result = session.run(query, rule_id=rule_id)
            record = result.single()

            if record:
                return {
                    "rule_id": record["rule_id"],
                    "rule_name": record["rule_name"],
                    "risk_level": record["risk_level"],
                    "description": record["description"],
                    "evidence_text": record["evidence_text"],
                    "guideline_source": record["guideline_source"],
                    "guideline_url": record["guideline_url"],
                    "criteria": record["criteria"],
                    "action": {
                        "type": record["action_type"],
                        "urgency": record["action_urgency"],
                        "rationale": record["action_rationale"],
                    }
                }
            return None


# =============================================================================
# 便捷函数
# =============================================================================

_reasoner = None


def get_reasoner() -> ClinicalRulesReasoner:
    """获取单例推理器"""
    global _reasoner
    if _reasoner is None:
        _reasoner = ClinicalRulesReasoner()
    return _reasoner


def reason_with_rules(
    symptom_sctids: List[str],
    symptom_keywords: List[str] = None,
    severity: str = "moderate"
) -> ReasoningResult:
    """
    使用临床规则进行推理 (便捷函数)
    """
    return get_reasoner().reason(symptom_sctids, symptom_keywords, severity)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Clinical Rules Reasoner Test")
    print("=" * 60)

    reasoner = ClinicalRulesReasoner()

    # 测试用例: TBI with vomiting
    print("\n--- Test 1: TBI with vomiting ---")
    result = reasoner.reason(
        symptom_sctids=["127295002", "422587007"],  # TBI, vomiting
        symptom_keywords=["head injury", "vomiting", "fell"],
        severity="moderate"
    )

    print(f"Matched Rules: {len(result.matched_rules)}")
    for rule in result.matched_rules:
        print(f"  - {rule.rule_name} [{rule.risk_level}] (coverage: {rule.coverage:.0%})")
        print(f"    Source: {rule.guideline_source}")

    print(f"\nHighest Risk: {result.highest_risk}")
    print(f"Confidence: {result.confidence:.0%}")

    if result.clarifying_questions:
        print(f"\nClarifying Questions:")
        for q in result.clarifying_questions[:3]:
            print(f"  - {q['question']}")

    if result.recommended_actions:
        print(f"\nRecommended Actions:")
        for a in result.recommended_actions[:3]:
            print(f"  - [{a['urgency']}] {a['type']}: {a['rationale']}")
