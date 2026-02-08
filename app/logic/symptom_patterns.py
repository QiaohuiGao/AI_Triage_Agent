"""
Extended Symptom Extraction Patterns
====================================

扩展的症状提取模式，覆盖高危疾病的特征表现。

包含:
- TBI 相关症状模式
- ACS/心脏相关症状模式
- PE 相关症状模式
- Stroke 相关症状模式
- Aortic Dissection 相关症状模式
- 时间维度提取 (onset, duration)
- 严重程度提取增强
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ExtractedSymptom:
    """提取的症状实体"""
    text: str                    # 原始文本
    category: str                # 症状类别
    snomed_hint: str = ""        # 建议的SNOMED code
    severity: str = "moderate"   # 严重程度
    onset: str = ""              # 发作方式 (sudden/gradual)
    duration: str = ""           # 持续时间
    location: str = ""           # 部位
    quality: str = ""            # 性质
    radiation: str = ""          # 放射


# =============================================================================
# 症状模式定义
# =============================================================================

# TBI 相关症状
TBI_PATTERNS = [
    # 头部外伤
    (r"\b(head\s*injury|head\s*trauma|hit\s*(?:my|his|her)?\s*head|fell\s*(?:and\s*)?hit\s*head)\b", "head_trauma", "127295002"),
    (r"\b(concussion|knocked\s*out|blacked\s*out)\b", "concussion", "110030002"),
    # Canadian CT Head Rule 症状
    (r"\b(vomit(?:ing|ed)?|threw\s*up|nausea)\b", "vomiting", "422587007"),
    (r"\b(memory\s*loss|amnesia|can(?:')?t\s*remember|don(?:')?t\s*remember)\b", "amnesia", "386807006"),
    (r"\b(confused|confusion|disoriented|altered\s*mental)\b", "confusion", "40917007"),
    (r"\b(seizure|convulsion|fit)\b", "seizure", "91175000"),
    (r"\b(unconscious|unresponsive|passed\s*out|lost\s*consciousness)\b", "loc", "419045004"),
    # 颅骨骨折征象
    (r"\b(raccoon\s*eyes?|bruising\s*around\s*eyes?)\b", "basal_skull_sign", "110266004"),
    (r"\b(battle(?:')?s?\s*sign|bruising\s*behind\s*ear)\b", "basal_skull_sign", "110266004"),
    (r"\b(fluid\s*from\s*(?:ear|nose)|csf\s*leak|clear\s*fluid)\b", "csf_leak", "110266004"),
    (r"\b(blood\s*from\s*ear|bleeding\s*(?:from\s*)?ear)\b", "ear_bleeding", "110266004"),
    # 机制
    (r"\b(fall|fell)\s*(?:from|off|down)?\s*(?:height|stairs?|ladder|roof|balcony)?\b", "fall", "242603007"),
    (r"\b(car\s*(?:accident|crash)|mva|motor\s*vehicle|auto\s*accident|traffic\s*accident)\b", "mva", "418399005"),
    (r"\b(pedestrian\s*(?:hit|struck)|hit\s*by\s*(?:car|vehicle))\b", "pedestrian_struck", "418399005"),
    (r"\b(bicycle|bike|cycling)\s*(?:accident|crash|fell)?\b", "bicycle_injury", "418399005"),
]

# ACS/心脏相关症状
CARDIAC_PATTERNS = [
    # 胸痛类型
    (r"\b(chest\s*pain|chest\s*discomfort|pain\s*in\s*(?:my\s*)?chest)\b", "chest_pain", "29857009"),
    (r"\b(crushing|pressure|squeezing|tightness|heaviness)\s*(?:in\s*)?(?:my\s*)?chest\b", "typical_angina", "426396005"),
    (r"\b(chest\s*(?:feels?\s*)?(?:tight|heavy|pressure))\b", "typical_angina", "426396005"),
    (r"\b(elephant\s*on\s*(?:my\s*)?chest|band\s*around\s*chest)\b", "typical_angina", "426396005"),
    # 放射痛
    (r"\b(pain|ache|discomfort)\s*(?:radiating?|going|spreading|moving)\s*(?:to|down|into)\s*(?:my\s*)?(arm|left\s*arm|shoulder)\b", "radiation_arm", "102588006"),
    (r"\b(left\s*arm\s*(?:pain|ache|numb|tingling))\b", "radiation_arm", "102588006"),
    (r"\b(pain|ache|discomfort)\s*(?:radiating?|going|spreading)\s*(?:to|into)\s*(?:my\s*)?(jaw|neck|throat)\b", "radiation_jaw", "102589003"),
    (r"\b(jaw\s*(?:pain|ache)|neck\s*pain\s*with\s*chest)\b", "radiation_jaw", "102589003"),
    # 伴随症状
    (r"\b(sweating|diaphoresis|cold\s*sweat|clammy|perspiring)\b", "diaphoresis", "415690000"),
    (r"\b(short(?:ness)?\s*of\s*breath|can(?:')?t\s*(?:catch\s*(?:my\s*)?)?breath|breathless|dyspnea)\b", "dyspnea", "267036007"),
    (r"\b(palpitation|heart\s*racing|heart\s*pounding|irregular\s*heartbeat)\b", "palpitation", "80313002"),
    # 心衰症状
    (r"\b(leg\s*swelling|ankle\s*swelling|edema|swollen\s*(?:legs?|ankles?|feet))\b", "leg_edema", "267038008"),
    (r"\b(can(?:')?t\s*lie\s*flat|orthopnea|wake\s*up\s*short\s*of\s*breath)\b", "orthopnea", "62744007"),
]

# PE 相关症状
PE_PATTERNS = [
    # 主症状
    (r"\b(pleuritic\s*(?:chest\s*)?pain|pain\s*worse\s*(?:with|on)\s*breath(?:ing)?)\b", "pleuritic_pain", "89138009"),
    (r"\b(sudden\s*short(?:ness)?\s*of\s*breath|acute\s*dyspnea)\b", "acute_dyspnea", "267036007"),
    (r"\b(cough(?:ing)?\s*(?:up\s*)?blood|hemoptysis|bloody\s*(?:sputum|phlegm))\b", "hemoptysis", "66857006"),
    # DVT症状
    (r"\b(leg\s*(?:pain|swelling|red(?:ness)?)|calf\s*(?:pain|swelling|tender(?:ness)?))\b", "dvt_signs", "128053003"),
    (r"\b(one\s*leg\s*(?:swollen|bigger|larger)|unilateral\s*(?:leg\s*)?(?:swelling|edema))\b", "unilateral_leg_swelling", "95573000"),
    # 风险因素
    (r"\b(recent\s*(?:surgery|operation)|just\s*had\s*surgery|post[\s\-]?op(?:erative)?)\b", "recent_surgery", "387713003"),
    (r"\b((?:long\s*)?(?:flight|travel|trip)|sitting\s*(?:for\s*)?long|immobil(?:e|ized|ity))\b", "immobilization", "102894008"),
    (r"\b(on\s*(?:birth\s*control|the\s*pill|estrogen|hormone|hrt))\b", "estrogen_use", "766989005"),
    (r"\b((?:blood\s*)?clot\s*(?:before|history|previous)|previous\s*(?:dvt|pe)|history\s*of\s*(?:dvt|pe|clot))\b", "vte_history", "161512007"),
    (r"\b(cancer|malignancy|tumor|chemo(?:therapy)?|oncology)\b", "malignancy", "363346000"),
]

# Stroke 相关症状 (FAST)
STROKE_PATTERNS = [
    # FAST症状
    (r"\b(face\s*droop(?:ing)?|facial\s*(?:weakness|droop|asymmetry)|one\s*side\s*of\s*face)\b", "facial_droop", "398979000"),
    (r"\b(smile\s*(?:is\s*)?uneven|crooked\s*smile|mouth\s*droop(?:ing)?)\b", "facial_droop", "398979000"),
    (r"\b(arm\s*(?:weakness|drift|numb(?:ness)?)|can(?:')?t\s*(?:lift|raise|move)\s*(?:my\s*)?arm)\b", "arm_weakness", "249966004"),
    (r"\b(leg\s*(?:weakness|drag(?:ging)?|numb(?:ness)?)|can(?:')?t\s*(?:walk|move)\s*(?:my\s*)?leg)\b", "leg_weakness", "249966004"),
    (r"\b(slur(?:red|ring)?\s*speech|speech\s*(?:difficulty|problem)|trouble\s*(?:speaking|talking))\b", "speech_difficulty", "29164008"),
    (r"\b(can(?:')?t\s*(?:speak|talk|find\s*words)|words?\s*(?:come\s*out)?\s*wrong)\b", "aphasia", "87486003"),
    # 其他卒中症状
    (r"\b(vision\s*(?:loss|problem|change)|can(?:')?t\s*see|blind(?:ness)?|double\s*vision)\b", "vision_change", "422400008"),
    (r"\b(sudden\s*(?:severe\s*)?headache|thunderclap\s*headache|worst\s*headache)\b", "thunderclap_headache", "25064002"),
    (r"\b(balance\s*(?:problem|loss)|loss\s*of\s*balance|can(?:')?t\s*(?:stand|walk\s*straight)|ataxia)\b", "ataxia", "20262006"),
    (r"\b(dizziness|vertigo|room\s*(?:is\s*)?spinning)\b", "vertigo", "399153001"),
    # 一侧症状
    (r"\b(one\s*side\s*(?:weak|numb|paralyzed)|(?:left|right)\s*side\s*(?:weak|numb))\b", "hemiparesis", "246636008"),
    (r"\b(half\s*(?:of\s*)?(?:my\s*)?body\s*(?:numb|weak|can(?:')?t\s*feel))\b", "hemiparesis", "246636008"),
]

# Aortic Dissection 相关症状
AORTIC_PATTERNS = [
    # 特征性疼痛
    (r"\b(tearing\s*(?:chest\s*)?pain|ripping\s*(?:chest\s*)?pain)\b", "tearing_pain", "426206001"),
    (r"\b(knife[\s\-]?like\s*pain|sharp\s*(?:severe\s*)?pain)\b", "sharp_pain", "426206001"),
    (r"\b(pain\s*(?:moving|radiating|spreading)\s*(?:to|into)\s*(?:my\s*)?back)\b", "back_radiation", "161891005"),
    (r"\b(back\s*pain\s*(?:with|and)\s*chest\s*pain)\b", "chest_back_pain", "161891005"),
    # 疼痛特点
    (r"\b(sudden(?:ly)?\s*(?:started|began|onset)|came\s*on\s*suddenly|abrupt(?:ly)?)\b", "sudden_onset", ""),
    (r"\b(worst\s*(?:pain\s*)?(?:of\s*my\s*life|ever|imaginable)|most\s*severe\s*pain)\b", "maximal_at_onset", ""),
    # 相关症状
    (r"\b(different\s*(?:blood\s*)?pressure|bp\s*different|pulse\s*different)\b", "bp_differential", "13213009"),
    (r"\b(weak(?:er)?\s*pulse|no\s*pulse|can(?:')?t\s*feel\s*pulse)\b", "pulse_deficit", "13213009"),
]

# 时间相关模式
ONSET_PATTERNS = [
    (r"\b(sudden(?:ly)?|abrupt(?:ly)?|all\s*of\s*a\s*sudden|out\s*of\s*(?:the\s*)?blue)\b", "sudden"),
    (r"\b(gradual(?:ly)?|slowly|over\s*time|getting\s*worse)\b", "gradual"),
    (r"\b(woke\s*up\s*with|this\s*morning|when\s*I\s*woke)\b", "upon_waking"),
    (r"\b(just\s*started|just\s*happened|(?:a\s*)?few\s*(?:minutes?|hours?)\s*ago)\b", "acute"),
]

DURATION_PATTERNS = [
    (r"(?:for\s*)?(\d+)\s*(second|minute|hour|day|week|month)s?\b", "extract"),
    (r"\b(constant|continuous|all\s*the\s*time|non[\s\-]?stop)\b", "constant"),
    (r"\b(comes?\s*and\s*goes?|intermittent|on\s*and\s*off)\b", "intermittent"),
    (r"\b(brief|short|momentary|fleeting)\b", "brief"),
]

# 严重程度模式 (增强版)
SEVERITY_PATTERNS = {
    "severe": [
        r"\b(severe|worst|terrible|excruciating|unbearable|extreme|intense|agonizing)\b",
        r"\b(10/10|10\s*out\s*of\s*10|9/10|9\s*out\s*of\s*10|8/10)\b",
        r"\b(can(?:')?t\s*(?:stand|bear|take)\s*(?:it|the\s*pain))\b",
        r"\b(worst\s*(?:pain\s*)?(?:ever|of\s*my\s*life))\b",
        r"\b(screaming|crying\s*(?:from|in)\s*pain)\b",
    ],
    "moderate": [
        r"\b(moderate|significant|noticeable|considerable)\b",
        r"\b(7/10|6/10|5/10)\b",
        r"\b(uncomfortable|bothering|annoying)\b",
    ],
    "mild": [
        r"\b(mild|slight|minor|little|small|light)\b",
        r"\b(1/10|2/10|3/10|4/10)\b",
        r"\b(not\s*(?:too\s*)?bad|manageable|tolerable)\b",
        r"\b(dull|achy|nagging)\b",
    ],
}


# =============================================================================
# 症状提取器
# =============================================================================

class SymptomExtractor:
    """症状提取器 - 使用扩展模式"""

    def __init__(self):
        # 合并所有模式
        self.all_patterns = (
            TBI_PATTERNS +
            CARDIAC_PATTERNS +
            PE_PATTERNS +
            STROKE_PATTERNS +
            AORTIC_PATTERNS
        )

    def extract(self, text: str) -> List[ExtractedSymptom]:
        """
        从文本中提取症状

        Args:
            text: 患者描述文本

        Returns:
            提取的症状列表
        """
        text_lower = text.lower()
        symptoms = []
        seen_categories = set()

        # 提取症状
        for pattern, category, snomed_hint in self.all_patterns:
            matches = re.findall(pattern, text_lower, re.I)
            if matches and category not in seen_categories:
                seen_categories.add(category)

                # 获取匹配的文本
                match_text = matches[0] if isinstance(matches[0], str) else matches[0][0] if matches[0] else ""

                symptom = ExtractedSymptom(
                    text=match_text.strip(),
                    category=category,
                    snomed_hint=snomed_hint,
                    severity=self._extract_severity(text_lower),
                    onset=self._extract_onset(text_lower),
                    duration=self._extract_duration(text_lower),
                )
                symptoms.append(symptom)

        return symptoms

    def _extract_severity(self, text: str) -> str:
        """提取严重程度"""
        for severity, patterns in SEVERITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    return severity
        return "moderate"

    def _extract_onset(self, text: str) -> str:
        """提取发作方式"""
        for pattern, onset_type in ONSET_PATTERNS:
            if re.search(pattern, text, re.I):
                return onset_type
        return ""

    def _extract_duration(self, text: str) -> str:
        """提取持续时间"""
        # 尝试提取具体时间
        match = re.search(r"(?:for\s*)?(\d+)\s*(second|minute|hour|day|week|month)s?\b", text, re.I)
        if match:
            return f"{match.group(1)} {match.group(2)}s"

        # 尝试提取模式
        for pattern, duration_type in DURATION_PATTERNS[1:]:  # Skip extract pattern
            if re.search(pattern, text, re.I):
                return duration_type
        return ""

    def get_keywords(self, text: str) -> List[str]:
        """
        获取症状关键词列表 (兼容旧接口)

        Args:
            text: 患者描述文本

        Returns:
            关键词列表
        """
        symptoms = self.extract(text)
        return [s.text for s in symptoms if s.text]


# =============================================================================
# 便捷函数
# =============================================================================

_extractor = None

def get_extractor() -> SymptomExtractor:
    """获取单例提取器"""
    global _extractor
    if _extractor is None:
        _extractor = SymptomExtractor()
    return _extractor


def extract_symptoms(text: str) -> List[ExtractedSymptom]:
    """提取症状 (便捷函数)"""
    return get_extractor().extract(text)


def extract_symptom_keywords(text: str) -> List[str]:
    """
    提取症状关键词 (兼容旧接口)

    可直接替换 parse_symptom.py 中的 extract_symptom_keywords
    """
    return get_extractor().get_keywords(text)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    test_cases = [
        "55 year old male, fell and hit his head, vomited twice, can't remember what happened",
        "Crushing chest pain radiating to left arm, sweating, short of breath",
        "Sudden severe headache, worst of my life, came on like a thunderclap",
        "One leg is swollen and painful, just got off a long flight",
        "Face drooping on one side, can't lift my arm, speech is slurred",
        "Tearing chest pain going into my back, started suddenly, 10/10 severe",
    ]

    extractor = SymptomExtractor()

    print("=" * 60)
    print("Symptom Extraction Test")
    print("=" * 60)

    for text in test_cases:
        print(f"\nInput: {text}")
        print("-" * 40)
        symptoms = extractor.extract(text)
        for s in symptoms:
            print(f"  [{s.category}] {s.text}")
            if s.severity != "moderate":
                print(f"    Severity: {s.severity}")
            if s.onset:
                print(f"    Onset: {s.onset}")
            if s.snomed_hint:
                print(f"    SNOMED: {s.snomed_hint}")
