"""
Schmitt-Thompson Style Triage Protocols
=======================================

这个模块提供基于症状的分诊协议，用于：
1. 生成排除性问题 (Red Flag Questions)
2. 评估症状严重程度
3. 确定相关风险因素
4. 支持 ESI 分级决策
"""

import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

# Protocol cache
_protocols: Dict[str, Dict] = {}


def _get_protocol_dir() -> Path:
    """获取协议目录路径"""
    return Path(__file__).parent


def load_protocol(symptom_key: str) -> Optional[Dict[str, Any]]:
    """
    加载特定症状的协议

    Args:
        symptom_key: 症状关键字 (如 "chest_pain", "headache")

    Returns:
        协议字典或 None
    """
    if symptom_key in _protocols:
        return _protocols[symptom_key]

    protocol_path = _get_protocol_dir() / f"{symptom_key}.json"
    if protocol_path.exists():
        with open(protocol_path, 'r', encoding='utf-8') as f:
            protocol = json.load(f)
            _protocols[symptom_key] = protocol
            return protocol

    return None


def get_available_protocols() -> List[str]:
    """获取所有可用的协议列表"""
    protocol_dir = _get_protocol_dir()
    return [
        f.stem for f in protocol_dir.glob("*.json")
        if f.stem != "__init__"
    ]


def find_protocol_by_snomed(sctid: str) -> Optional[Dict[str, Any]]:
    """
    通过 SNOMED 代码查找协议

    Args:
        sctid: SNOMED CT concept ID

    Returns:
        匹配的协议或 None
    """
    # 加载所有协议
    for protocol_name in get_available_protocols():
        protocol = load_protocol(protocol_name)
        if protocol and sctid in protocol.get("snomed_codes", []):
            return protocol

    return None


def find_protocol_by_symptom(symptom_text: str) -> Optional[Dict[str, Any]]:
    """
    通过症状文本查找协议 (模糊匹配)

    Args:
        symptom_text: 症状描述文本

    Returns:
        最匹配的协议或 None
    """
    symptom_lower = symptom_text.lower()

    # 关键词映射
    keyword_map = {
        "chest_pain": ["chest", "cardiac", "heart", "angina"],
        "headache": ["headache", "head pain", "migraine", "cephalgia"],
        "abdominal_pain": ["abdominal", "stomach", "belly", "abdomen", "tummy"],
        "shortness_of_breath": ["breath", "breathing", "dyspnea", "respiratory"],
        "fever": ["fever", "febrile", "temperature", "chills"],
    }

    for protocol_key, keywords in keyword_map.items():
        if any(kw in symptom_lower for kw in keywords):
            protocol = load_protocol(protocol_key)
            if protocol:
                return protocol

    return None


def get_red_flags(protocol: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从协议中提取 Red Flag 问题"""
    return protocol.get("red_flags", [])


def get_severity_questions(protocol: Dict[str, Any]) -> List[str]:
    """从协议中提取严重程度评估问题"""
    severity = protocol.get("severity_assessment", {})
    return severity.get("questions", [])


def match_red_flag_keywords(
    protocol: Dict[str, Any],
    patient_response: str
) -> List[Dict[str, Any]]:
    """
    检查患者回答是否触发 Red Flag

    Args:
        protocol: 协议字典
        patient_response: 患者的回答文本

    Returns:
        触发的 Red Flag 列表
    """
    triggered = []
    response_lower = patient_response.lower()

    for red_flag in protocol.get("red_flags", []):
        keywords = red_flag.get("keywords", [])
        if any(kw.lower() in response_lower for kw in keywords):
            triggered.append(red_flag)

    return triggered
