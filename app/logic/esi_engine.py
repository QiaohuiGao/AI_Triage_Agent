"""
ESI Logic Engine (esi_engine.py)
================================
Emergency Severity Index (ESI) 五级分诊引擎

ESI 是急诊分诊的金标准，基于以下四个决策点：
- Decision A: 是否需要立即抢救？(ESI 1)
- Decision B: 是否属于高危情况？(ESI 2)
- Decision C: 需要多少医疗资源？(ESI 3-5)
- Decision D: 生命体征是否异常？(可能升级至 ESI 2)

参考文献:
- ESI Handbook v4 (AHRQ)
- Gilboy N, et al. Emergency Severity Index Implementation Handbook

Red Flag Codes来源:
- Canadian CT Head Rule (TBI)
- HEART Score / TIMI Risk (ACS/AMI)
- Wells Criteria / PERC Rule (PE)
- Stanford Classification (Aortic Dissection)
- FAST / NIH Stroke Scale (Stroke)
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import IntEnum

# 导入扩展的Red Flag代码库
from app.logic.red_flag_codes import (
    ALL_RED_FLAG_CODES,
    LEVEL_1_SCTIDS,
    LEVEL_2_SCTIDS,
    CONDITIONAL_SCTIDS,
    RiskLevel,
    get_red_flag_info,
    check_red_flags,
    get_highest_risk_level,
)


class ESILevel(IntEnum):
    """ESI 分级枚举"""
    LEVEL_1 = 1  # 立即抢救 (Resuscitation)
    LEVEL_2 = 2  # 高危紧急 (Emergent)
    LEVEL_3 = 3  # 紧急 (Urgent) - 需要2+资源
    LEVEL_4 = 4  # 较紧急 (Less Urgent) - 需要1资源
    LEVEL_5 = 5  # 非紧急 (Non-urgent) - 无需资源


@dataclass
class ESIAssessment:
    """ESI 评估结果"""
    level: ESILevel
    decision_point: str  # A, B, C, or D
    rationale: str
    red_flags: List[str] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    confidence: float = 1.0
    resource_estimate: int = 0


# ========== RED FLAG SNOMED CODES ==========
# 从 red_flag_codes.py 导入，保留兼容性别名

# ESI Level 1: 立即威胁生命的状态 (CRITICAL)
LEVEL_1_CODES = {
    sctid: ALL_RED_FLAG_CODES[sctid].name
    for sctid in LEVEL_1_SCTIDS
    if sctid in ALL_RED_FLAG_CODES
}

# ESI Level 2: 高危情况 (HIGH)
LEVEL_2_CODES = {
    sctid: ALL_RED_FLAG_CODES[sctid].name
    for sctid in LEVEL_2_SCTIDS
    if sctid in ALL_RED_FLAG_CODES
}

# ESI Level 2: 需要检查严重程度的代码 (CONDITIONAL)
LEVEL_2_SEVERITY_DEPENDENT = {
    sctid: ALL_RED_FLAG_CODES[sctid].name
    for sctid in CONDITIONAL_SCTIDS
    if sctid in ALL_RED_FLAG_CODES
}

# 需要关注的解剖部位 (Finding Site)
HIGH_RISK_SITES = {
    "80891009": "Heart",
    "12738006": "Brain",
    "39607008": "Lung",
    "181268008": "Coronary artery",
    "15497006": "Aorta",
    "113305005": "Cervical spine",
    "69536005": "Head",
    "302509004": "Thorax",
    "818983003": "Abdomen",
}

# 需要关注的病理形态 (Associated Morphology)
HIGH_RISK_MORPHOLOGIES = {
    "55641003": "Infarction",
    "50960005": "Hemorrhage",
    "26036001": "Obstruction",
    "36118008": "Perforation",
    "30782001": "Rupture",
    "112639008": "Thrombosis",
    "1806006": "Dissection",
    "414086009": "Embolism",
}


class ESIEngine:
    """
    ESI 五级分诊引擎

    实现 ESI v4 的四个决策点逻辑
    """

    def __init__(self, graph_service=None):
        """
        初始化 ESI 引擎

        Args:
            graph_service: Neo4j 图服务实例，用于查询 SNOMED 关系
        """
        self.graph_service = graph_service

    def assess(
        self,
        symptoms: List[Dict[str, Any]],
        vitals: Optional[Dict[str, Any]] = None,
        graph_context: Optional[Dict[str, Any]] = None
    ) -> ESIAssessment:
        """
        执行 ESI 评估

        Args:
            symptoms: 症状列表，每个包含 sctid, fsn, severity 等
            vitals: 生命体征 (可选) - HR, RR, SpO2, BP, Temp
            graph_context: Neo4j 图查询的上下文信息

        Returns:
            ESIAssessment 评估结果
        """
        # Decision Point A: 是否需要立即抢救？
        result = self._decision_a_life_threat(symptoms, vitals)
        if result:
            return result

        # Decision Point B: 是否属于高危情况？
        result = self._decision_b_high_risk(symptoms, vitals, graph_context)
        if result:
            return result

        # Decision Point C: 需要多少医疗资源？
        result = self._decision_c_resources(symptoms, graph_context)

        # Decision Point D: 检查生命体征是否需要升级
        if vitals:
            result = self._decision_d_vitals_check(result, vitals)

        return result

    def _decision_a_life_threat(
        self,
        symptoms: List[Dict[str, Any]],
        vitals: Optional[Dict[str, Any]]
    ) -> Optional[ESIAssessment]:
        """
        Decision Point A: 立即威胁生命的情况

        检查:
        - 心跳/呼吸骤停
        - 严重呼吸窘迫
        - 过敏性休克
        - 无反应/昏迷
        - 休克状态
        - 大出血

        使用扩展的Red Flag代码库 (LEVEL_1_CRITICAL codes)
        """
        red_flags = []
        actions = []

        # 检查症状中是否有 Level 1 代码
        for symptom in symptoms:
            sctid = symptom.get("sctid", "")

            # 优先使用增强的Red Flag信息
            flag_info = get_red_flag_info(sctid)
            if flag_info and flag_info.risk_level == RiskLevel.CRITICAL:
                red_flags.append(
                    f"{flag_info.name_zh} ({flag_info.name}) [来源: {flag_info.guideline_source}]"
                )
                actions.append(flag_info.action)
            elif sctid in LEVEL_1_CODES:
                # 兼容旧逻辑
                red_flags.append(f"{LEVEL_1_CODES[sctid]} (SCTID: {sctid})")

        # 检查生命体征是否危急
        if vitals:
            if vitals.get("hr", 80) == 0 or vitals.get("rr", 16) == 0:
                red_flags.append("心跳或呼吸停止")
            if vitals.get("spo2", 98) < 80:
                red_flags.append(f"严重低氧血症 (SpO2: {vitals.get('spo2')}%)")
            if vitals.get("gcs", 15) <= 8:
                red_flags.append(f"严重意识障碍 (GCS: {vitals.get('gcs')})")

        if red_flags:
            # 构建包含建议动作的rationale
            rationale = "检测到需要立即抢救的情况"
            if actions:
                rationale += f"。建议: {'; '.join(set(actions))}"

            return ESIAssessment(
                level=ESILevel.LEVEL_1,
                decision_point="A",
                rationale=rationale,
                red_flags=red_flags,
                confidence=1.0,
                resource_estimate=5  # 最高资源需求
            )

        return None

    def _decision_b_high_risk(
        self,
        symptoms: List[Dict[str, Any]],
        vitals: Optional[Dict[str, Any]],
        graph_context: Optional[Dict[str, Any]]
    ) -> Optional[ESIAssessment]:
        """
        Decision Point B: 高危情况

        检查:
        - 不应该等待的情况
        - 意识改变、神志不清
        - 严重疼痛/窘迫
        - 高危症状组合

        使用扩展的Red Flag代码库 (100+ codes from clinical guidelines)
        """
        red_flags = []
        red_flag_details = []  # 详细信息用于追溯
        requires_clarification = False
        clarification_questions = []

        # 检查症状中是否有 Level 2 代码
        severe_indicators = ["severe", "10/10", "9/10", "8/10", "7/10", "worst", "sudden", "thunderclap"]

        for symptom in symptoms:
            sctid = symptom.get("sctid", "")
            severity = symptom.get("severity", "moderate")
            symptom_text = symptom.get("symptom", "").lower()

            # 使用增强的Red Flag检查
            flag_info = get_red_flag_info(sctid)

            if flag_info:
                if flag_info.risk_level == RiskLevel.HIGH:
                    # 始终高危的代码
                    red_flags.append(
                        f"{flag_info.name_zh} ({flag_info.name}) [来源: {flag_info.guideline_source}]"
                    )
                    red_flag_details.append({
                        "sctid": sctid,
                        "name": flag_info.name,
                        "category": flag_info.category,
                        "guideline": flag_info.guideline_source,
                        "action": flag_info.action
                    })

                elif flag_info.risk_level == RiskLevel.CONDITIONAL:
                    # 需要结合严重程度判断
                    is_severe = severity in severe_indicators or any(ind in symptom_text for ind in severe_indicators)
                    if is_severe:
                        red_flags.append(
                            f"{flag_info.name_zh} - 严重 [来源: {flag_info.guideline_source}]"
                        )
                        red_flag_details.append({
                            "sctid": sctid,
                            "name": flag_info.name,
                            "category": flag_info.category,
                            "guideline": flag_info.guideline_source,
                            "action": flag_info.action,
                            "severity_triggered": True
                        })
                    else:
                        # 非严重 - 需要追问
                        requires_clarification = True

            else:
                # 兼容旧逻辑: 检查旧的hardcoded codes
                if sctid in LEVEL_2_CODES:
                    red_flags.append(f"{LEVEL_2_CODES[sctid]} (SCTID: {sctid})")
                elif sctid in LEVEL_2_SEVERITY_DEPENDENT:
                    is_severe = severity in severe_indicators or any(ind in symptom_text for ind in severe_indicators)
                    if is_severe:
                        red_flags.append(f"{LEVEL_2_SEVERITY_DEPENDENT[sctid]} - Severe (SCTID: {sctid})")
                    else:
                        requires_clarification = True

            # 严重疼痛 (7-10/10) - 独立检查
            if severity in severe_indicators:
                red_flags.append(f"严重疼痛: {symptom.get('fsn', symptom.get('symptom'))}")

        # 使用图上下文检查高危关联
        if graph_context:
            # 检查是否关联高危解剖部位
            finding_sites = graph_context.get("finding_sites", [])
            for site in finding_sites:
                if site.get("sctid") in HIGH_RISK_SITES:
                    red_flags.append(f"高危部位: {site.get('fsn')}")

            # 检查是否关联高危病理
            morphologies = graph_context.get("morphologies", [])
            for morph in morphologies:
                if morph.get("sctid") in HIGH_RISK_MORPHOLOGIES:
                    red_flags.append(f"高危病理: {morph.get('fsn')}")

            # 检查 ISA 关系中是否包含高危父类
            ancestors = graph_context.get("ancestors", [])
            for ancestor in ancestors:
                if ancestor.get("sctid") in LEVEL_2_CODES:
                    red_flags.append(f"属于高危类别: {ancestor.get('fsn')}")

        # 特殊组合检测：胸痛 + 呼吸困难
        symptom_names = [s.get("symptom", "").lower() for s in symptoms]
        if "chest pain" in symptom_names or "chest" in " ".join(symptom_names):
            if "breath" in " ".join(symptom_names) or "dyspnea" in " ".join(symptom_names):
                red_flags.append("胸痛 + 呼吸困难组合 (可能心脏事件)")

        # 如果检测到部分高危信号但不确定，需要追问
        if len(red_flags) == 1:
            requires_clarification = True
            clarification_questions = self._generate_level2_questions(symptoms)

        if red_flags:
            return ESIAssessment(
                level=ESILevel.LEVEL_2,
                decision_point="B",
                rationale="检测到高危情况，需要紧急处理",
                red_flags=red_flags,
                requires_clarification=requires_clarification,
                clarification_questions=clarification_questions,
                confidence=0.9 if requires_clarification else 1.0,
                resource_estimate=4
            )

        return None

    def _decision_c_resources(
        self,
        symptoms: List[Dict[str, Any]],
        graph_context: Optional[Dict[str, Any]]
    ) -> ESIAssessment:
        """
        Decision Point C: 资源需求评估

        资源定义:
        - Labs (血检)
        - ECG
        - X-rays, CT, MRI
        - IV fluids
        - Specialty consultation

        ESI 3: 需要 2+ 资源
        ESI 4: 需要 1 资源
        ESI 5: 无需资源
        """
        resource_count = 0
        resources_needed = []

        # 基于症状估计资源需求
        for symptom in symptoms:
            sctid = symptom.get("sctid", "")
            symptom_text = symptom.get("symptom", "").lower()

            # 疼痛通常需要检查
            if "pain" in symptom_text:
                if "chest" in symptom_text or "abdominal" in symptom_text:
                    resources_needed.extend(["Labs", "ECG", "Imaging"])
                elif "head" in symptom_text:
                    resources_needed.extend(["Labs", "CT"])
                else:
                    resources_needed.append("Exam")

            # 发热需要血检
            if "fever" in symptom_text:
                resources_needed.extend(["Labs", "Exam"])

            # 呼吸问题需要多项检查
            if "breath" in symptom_text or "cough" in symptom_text:
                resources_needed.extend(["X-ray", "SpO2", "Labs"])

            # 外伤需要影像
            if "injury" in symptom_text or "trauma" in symptom_text:
                resources_needed.extend(["X-ray", "CT"])

        # 使用图上下文估计资源
        if graph_context:
            procedures = graph_context.get("related_procedures", [])
            for proc in procedures:
                resources_needed.append(proc.get("fsn", "Procedure"))

        # 去重并计数
        unique_resources = list(set(resources_needed))
        resource_count = len(unique_resources)

        # 确定 ESI 等级
        if resource_count >= 2:
            level = ESILevel.LEVEL_3
            rationale = f"预计需要 {resource_count} 项医疗资源"
        elif resource_count == 1:
            level = ESILevel.LEVEL_4
            rationale = f"预计需要 1 项医疗资源: {unique_resources[0]}"
        else:
            level = ESILevel.LEVEL_5
            rationale = "无需额外医疗资源，可门诊处理"

        return ESIAssessment(
            level=level,
            decision_point="C",
            rationale=rationale,
            confidence=0.85,
            resource_estimate=resource_count
        )

    def _decision_d_vitals_check(
        self,
        current_assessment: ESIAssessment,
        vitals: Dict[str, Any]
    ) -> ESIAssessment:
        """
        Decision Point D: 生命体征检查

        如果当前为 ESI 3-5，但生命体征异常，可能升级为 ESI 2

        危险区域生命体征:
        - HR < 50 or > 100 (成人)
        - RR < 12 or > 20
        - SpO2 < 92%
        """
        if current_assessment.level.value <= 2:
            return current_assessment  # 已经是高优先级

        danger_signs = []

        hr = vitals.get("hr")
        if hr and (hr < 50 or hr > 100):
            danger_signs.append(f"心率异常: {hr} bpm")

        rr = vitals.get("rr")
        if rr and (rr < 12 or rr > 20):
            danger_signs.append(f"呼吸频率异常: {rr}/min")

        spo2 = vitals.get("spo2")
        if spo2 and spo2 < 92:
            danger_signs.append(f"低氧血症: SpO2 {spo2}%")

        temp = vitals.get("temp")
        if temp and (temp < 35 or temp > 39.5):
            danger_signs.append(f"体温异常: {temp}°C")

        # 如果有危险体征，考虑升级
        if danger_signs:
            return ESIAssessment(
                level=ESILevel.LEVEL_2,
                decision_point="D",
                rationale="生命体征异常，升级为 ESI Level 2",
                red_flags=current_assessment.red_flags + danger_signs,
                confidence=0.95,
                resource_estimate=current_assessment.resource_estimate + 1
            )

        return current_assessment

    def _generate_level2_questions(
        self,
        symptoms: List[Dict[str, Any]]
    ) -> List[str]:
        """
        生成 ESI Level 2 排除性问题

        基于 Schmitt-Thompson 风格的 Red Flag 问题
        """
        questions = []
        symptom_names = [s.get("symptom", "").lower() for s in symptoms]

        # 胸痛追问
        if any("chest" in s for s in symptom_names):
            questions.extend([
                "Is the pain crushing, squeezing, or pressure-like?",
                "Does the pain radiate to your arm, jaw, or back?",
                "Are you experiencing shortness of breath, sweating, or nausea?"
            ])

        # 头痛追问
        if any("headache" in s or "head" in s for s in symptom_names):
            questions.extend([
                "Is this the worst headache of your life?",
                "Did it come on suddenly (thunderclap)?",
                "Do you have neck stiffness or sensitivity to light?"
            ])

        # 腹痛追问
        if any("abdominal" in s or "stomach" in s for s in symptom_names):
            questions.extend([
                "Is the pain constant and getting worse?",
                "Do you have fever or vomiting blood?",
                "Is your abdomen rigid or distended?"
            ])

        # 呼吸问题追问
        if any("breath" in s or "breathing" in s for s in symptom_names):
            questions.extend([
                "Can you speak in full sentences?",
                "Are your lips or fingernails turning blue?",
                "Did this come on suddenly?"
            ])

        return questions[:3]  # 最多返回 3 个问题


# ========== 便捷函数 ==========

def calculate_esi(
    symptoms: List[Dict[str, Any]],
    vitals: Optional[Dict[str, Any]] = None,
    graph_context: Optional[Dict[str, Any]] = None
) -> ESIAssessment:
    """
    计算 ESI 分级的便捷函数

    Args:
        symptoms: 症状列表
        vitals: 生命体征 (可选)
        graph_context: 图查询上下文 (可选)

    Returns:
        ESIAssessment 评估结果

    Example:
        >>> symptoms = [{"symptom": "chest pain", "sctid": "29857009", "severity": "severe"}]
        >>> result = calculate_esi(symptoms)
        >>> print(f"ESI Level: {result.level}, Rationale: {result.rationale}")
    """
    engine = ESIEngine()
    return engine.assess(symptoms, vitals, graph_context)


def is_high_risk(symptoms: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    快速检查是否为高危情况

    Returns:
        (is_high_risk, red_flags)
    """
    result = calculate_esi(symptoms)
    return result.level.value <= 2, result.red_flags


# ========== 测试代码 ==========
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        {
            "name": "Cardiac Arrest (ESI 1)",
            "symptoms": [{"symptom": "cardiac arrest", "sctid": "410429000"}],
            "expected": 1
        },
        {
            "name": "Severe Chest Pain (ESI 2)",
            "symptoms": [
                {"symptom": "chest pain", "sctid": "29857009", "severity": "severe"},
                {"symptom": "shortness of breath", "sctid": "267036007"}
            ],
            "expected": 2
        },
        {
            "name": "Fever + Cough (ESI 3)",
            "symptoms": [
                {"symptom": "fever", "sctid": "386661006"},
                {"symptom": "cough", "sctid": "49727002"}
            ],
            "expected": 3
        },
        {
            "name": "Minor Headache (ESI 4-5)",
            "symptoms": [
                {"symptom": "headache", "sctid": "25064002", "severity": "mild"}
            ],
            "expected": 4
        }
    ]

    engine = ESIEngine()

    print("=" * 60)
    print("ESI Engine Test Cases")
    print("=" * 60)

    for case in test_cases:
        result = engine.assess(case["symptoms"])
        status = "✓" if result.level.value == case["expected"] else "✗"
        print(f"\n{status} {case['name']}")
        print(f"  Expected: ESI {case['expected']}, Got: ESI {result.level.value}")
        print(f"  Decision Point: {result.decision_point}")
        print(f"  Rationale: {result.rationale}")
        if result.red_flags:
            print(f"  Red Flags: {result.red_flags}")
