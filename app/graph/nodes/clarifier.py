"""
Dynamic Clarifier Node (clarifier.py)
=====================================
基于 Schmitt-Thompson 风格的动态追问节点

功能：
- 当 ESI 评估不确定时，生成排除性问题
- 检测 Red Flags 并更新风险评估
- 限制追问轮数，保证用户体验

输入：GraphState (with ESI assessment)
输出：GraphState (with clarification questions or final assessment)
"""

from typing import List, Dict, Any, Optional
from app.schemas import GraphState
from app.logic.esi_engine import ESIAssessment, ESILevel
from app import protocols

# 最大追问轮数
MAX_CLARIFICATION_ROUNDS = 2


def should_clarify(state: GraphState) -> bool:
    """
    判断是否需要追问

    条件：
    1. ESI 评估标记需要澄清
    2. 未超过最大追问轮数
    3. 存在可用的协议问题
    """
    # 检查追问轮数
    clarification_count = getattr(state, "clarification_count", 0)
    if clarification_count >= MAX_CLARIFICATION_ROUNDS:
        return False

    # 检查 ESI 评估是否需要澄清
    esi_assessment = getattr(state, "esi_assessment", None)
    if esi_assessment and hasattr(esi_assessment, "requires_clarification"):
        return esi_assessment.requires_clarification

    # 检查是否有中等置信度的 ESI 评估
    if esi_assessment and hasattr(esi_assessment, "confidence"):
        if 0.6 < esi_assessment.confidence < 0.9:
            return True

    return False


def generate_clarification_questions(state: GraphState) -> List[str]:
    """
    生成追问问题

    基于：
    1. ESI 评估生成的问题
    2. 协议中的 Red Flag 问题
    3. 严重程度评估问题
    """
    questions = []

    # 从 ESI 评估获取问题
    esi_assessment = getattr(state, "esi_assessment", None)
    if esi_assessment and hasattr(esi_assessment, "clarification_questions"):
        questions.extend(esi_assessment.clarification_questions)

    # 从协议获取问题
    entities = getattr(state, "entities", [])
    for entity in entities:
        symptom = entity.get("symptom", "")
        protocol = protocols.find_protocol_by_symptom(symptom)

        if protocol:
            # 获取 Red Flag 问题
            red_flags = protocols.get_red_flags(protocol)
            for rf in red_flags:
                # 每个 Red Flag 取第一个问题
                rf_questions = rf.get("questions", [])
                if rf_questions:
                    questions.append(rf_questions[0])

    # 去重并限制数量
    seen = set()
    unique_questions = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique_questions.append(q)

    return unique_questions[:3]  # 最多 3 个问题


def process_clarification_response(
    state: GraphState,
    response: str
) -> Dict[str, Any]:
    """
    处理患者的追问回答

    返回：
    - triggered_red_flags: 触发的 Red Flags
    - severity_indicators: 严重程度指标
    - esi_adjustment: ESI 等级调整建议
    """
    result = {
        "triggered_red_flags": [],
        "severity_indicators": [],
        "esi_adjustment": None
    }

    response_lower = response.lower()

    # 检查肯定/否定回答
    positive_indicators = ["yes", "yeah", "correct", "true", "affirmative", "是", "对"]
    negative_indicators = ["no", "nope", "negative", "false", "不", "没有"]

    is_positive = any(ind in response_lower for ind in positive_indicators)
    is_negative = any(ind in response_lower for ind in negative_indicators)

    # 遍历相关协议检查 Red Flags
    entities = getattr(state, "entities", [])
    for entity in entities:
        symptom = entity.get("symptom", "")
        protocol = protocols.find_protocol_by_symptom(symptom)

        if protocol:
            triggered = protocols.match_red_flag_keywords(protocol, response)
            result["triggered_red_flags"].extend(triggered)

    # 如果触发了 Red Flags，建议调整 ESI
    if result["triggered_red_flags"]:
        # 获取最高优先级的 action
        for rf in result["triggered_red_flags"]:
            action = rf.get("positive_action", "")
            if action == "ESI_LEVEL_1":
                result["esi_adjustment"] = ESILevel.LEVEL_1
                break
            elif action == "ESI_LEVEL_2":
                if result["esi_adjustment"] != ESILevel.LEVEL_1:
                    result["esi_adjustment"] = ESILevel.LEVEL_2

    # 检查严重程度关键词
    severity_keywords = {
        "severe": ["severe", "worst", "unbearable", "10/10", "excruciating"],
        "moderate": ["moderate", "significant", "7/10", "8/10"],
        "mild": ["mild", "slight", "minor", "2/10", "3/10"]
    }

    for level, keywords in severity_keywords.items():
        if any(kw in response_lower for kw in keywords):
            result["severity_indicators"].append(level)

    return result


def clarify_node(state: GraphState) -> GraphState:
    """
    动态追问节点 - LangGraph 节点函数

    工作流程：
    1. 检查是否需要追问
    2. 如果需要，生成问题并标记状态
    3. 如果有回答，处理并更新 ESI 评估
    """
    # 检查是否需要追问
    if not should_clarify(state):
        state.needs_clarification = False
        return state

    # 检查是否有待处理的追问回答
    clarification_response = getattr(state, "clarification_response", None)

    if clarification_response:
        # 处理回答
        result = process_clarification_response(state, clarification_response)

        # 更新状态
        if result["triggered_red_flags"]:
            existing_flags = getattr(state, "red_flags", [])
            state.red_flags = existing_flags + [
                rf.get("condition") for rf in result["triggered_red_flags"]
            ]

        # 调整 ESI
        if result["esi_adjustment"]:
            esi_assessment = getattr(state, "esi_assessment", None)
            if esi_assessment:
                # 只能升级，不能降级
                if result["esi_adjustment"].value < esi_assessment.level.value:
                    state.esi_assessment = ESIAssessment(
                        level=result["esi_adjustment"],
                        decision_point="Clarification",
                        rationale=f"Red flag triggered: {result['triggered_red_flags'][0].get('condition')}",
                        red_flags=state.red_flags,
                        requires_clarification=False,
                        confidence=0.95
                    )

        # 增加追问计数
        state.clarification_count = getattr(state, "clarification_count", 0) + 1
        state.clarification_response = None  # 清除已处理的回答
        state.needs_clarification = False

    else:
        # 生成追问问题
        questions = generate_clarification_questions(state)

        if questions:
            state.clarification_questions = questions
            state.needs_clarification = True
        else:
            state.needs_clarification = False

    return state


def format_clarification_output(state: GraphState) -> Dict[str, Any]:
    """
    格式化追问输出供前端显示

    Returns:
        {
            "needs_clarification": bool,
            "questions": List[str],
            "context": str
        }
    """
    if not getattr(state, "needs_clarification", False):
        return {
            "needs_clarification": False,
            "questions": [],
            "context": ""
        }

    questions = getattr(state, "clarification_questions", [])

    # 生成上下文说明
    entities = getattr(state, "entities", [])
    symptoms = [e.get("symptom", "") for e in entities]
    context = f"Based on your symptoms ({', '.join(symptoms)}), I need to ask a few more questions to better assess your condition."

    return {
        "needs_clarification": True,
        "questions": questions,
        "context": context
    }


# ========== 测试代码 ==========
if __name__ == "__main__":
    from dataclasses import dataclass, field
    from typing import List, Dict, Any, Optional

    # 模拟 GraphState
    @dataclass
    class MockState:
        entities: List[Dict] = field(default_factory=list)
        esi_assessment: Optional[Any] = None
        clarification_count: int = 0
        clarification_response: Optional[str] = None
        clarification_questions: List[str] = field(default_factory=list)
        needs_clarification: bool = False
        red_flags: List[str] = field(default_factory=list)

    print("=" * 60)
    print("Dynamic Clarifier Test")
    print("=" * 60)

    # 测试：胸痛场景
    state = MockState(
        entities=[{"symptom": "chest pain", "sctid": "29857009"}],
        esi_assessment=ESIAssessment(
            level=ESILevel.LEVEL_3,
            decision_point="C",
            rationale="Initial assessment",
            requires_clarification=True,
            confidence=0.7
        )
    )

    print("\n1. Initial state with chest pain:")
    state = clarify_node(state)
    output = format_clarification_output(state)
    print(f"   Needs clarification: {output['needs_clarification']}")
    print(f"   Questions: {output['questions']}")

    # 模拟患者回答
    print("\n2. Patient responds with red flag indicators:")
    state.clarification_response = "Yes, the pain is crushing and radiates to my left arm"
    state = clarify_node(state)
    print(f"   Red flags detected: {state.red_flags}")
    if state.esi_assessment:
        print(f"   Updated ESI: Level {state.esi_assessment.level.value}")
