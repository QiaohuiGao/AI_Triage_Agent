"""
Symptom-Disease Knowledge Base
==============================

This module provides the core knowledge base for symptom-to-disease reasoning.
It combines:
1. Neo4j SNOMED CT relationships
2. Custom symptom-disease probability mappings
3. Red flag detection rules
4. Triage decision logic (ESI-based)

Architecture:
    Patient symptoms → Symptom normalization (SNOMED CT)
                    → Symptom pattern matching
                    → Disease probability calculation
                    → Triage level determination
"""

import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class TriageLevel(Enum):
    """ESI (Emergency Severity Index) based triage levels"""
    RED = 1      # Immediate - life threatening
    ORANGE = 2   # Emergent - high risk
    YELLOW = 3   # Urgent - needs attention soon
    GREEN = 4    # Less urgent - can wait
    BLUE = 5     # Non-urgent - can be scheduled


class UrgencyLevel(Enum):
    """Simplified urgency for patient communication"""
    EMERGENCY = "emergency"      # 立即急救
    URGENT = "urgent"            # 尽快就医
    SOON = "soon"                # 今天就医
    ROUTINE = "routine"          # 可预约就医


@dataclass
class SymptomPattern:
    """A pattern of symptoms that suggests certain conditions"""
    pattern_id: str
    symptoms: List[str]  # SNOMED CT codes
    symptom_names: List[str]  # Human readable names
    required_count: int = 1  # How many symptoms must match


@dataclass
class DiseaseCandidate:
    """A potential disease diagnosis with probability"""
    sctid: str
    name: str
    probability: float  # 0.0 to 1.0
    evidence: List[str]  # Which symptoms support this
    triage_level: TriageLevel
    department: str
    icd10_code: Optional[str] = None


@dataclass
class TriageResult:
    """Final triage decision output"""
    urgency: UrgencyLevel
    triage_level: TriageLevel
    primary_condition: Optional[DiseaseCandidate]
    differential_diagnosis: List[DiseaseCandidate]
    recommended_department: str
    recommended_action: str
    red_flags_detected: List[str]
    confidence: float


# ---------------------------------------------------------------------------
# Symptom-Disease Mapping Knowledge Base
# ---------------------------------------------------------------------------

# Core symptom-disease relationships
# Format: {symptom_pattern: [(disease_sctid, disease_name, base_probability, triage_level, department), ...]}

SYMPTOM_DISEASE_RULES: Dict[str, List[Dict]] = {

    # === CARDIAC EMERGENCIES ===
    "chest_pain_cardiac": {
        "pattern": {
            "required": ["29857009"],  # Chest pain
            "supporting": [
                "10000006",   # Radiating chest pain
                "415690000",  # Sweating (diaphoresis)
                "267036007",  # Dyspnea (shortness of breath)
                "84229001",   # Fatigue
                "422587007",  # Nausea
            ],
            "required_match": 1,
            "supporting_match": 2,  # Need at least 2 supporting symptoms
        },
        "conditions": [
            {
                "sctid": "22298006",
                "name": "Myocardial infarction (Heart attack)",
                "name_zh": "急性心肌梗死",
                "probability": 0.7,
                "triage_level": TriageLevel.RED,
                "department": "Emergency/Cardiology",
                "icd10": "I21.9",
            },
            {
                "sctid": "194828000",
                "name": "Angina pectoris",
                "name_zh": "心绞痛",
                "probability": 0.5,
                "triage_level": TriageLevel.ORANGE,
                "department": "Cardiology",
                "icd10": "I20.9",
            },
        ]
    },

    "chest_pain_anxiety": {
        "pattern": {
            "required": ["29857009"],  # Chest pain
            "supporting": [
                "48694002",   # Anxiety
                "271823003",  # Tachycardia (fast heart rate)
                "23141003",   # Hyperventilation
                "55929007",   # Feeling of impending doom
            ],
            "required_match": 1,
            "supporting_match": 2,
        },
        "conditions": [
            {
                "sctid": "371631005",
                "name": "Panic disorder",
                "name_zh": "惊恐发作",
                "probability": 0.6,
                "triage_level": TriageLevel.YELLOW,
                "department": "Psychiatry/Emergency",
                "icd10": "F41.0",
            },
        ]
    },

    # === RESPIRATORY ===
    "respiratory_infection": {
        "pattern": {
            "required": ["49727002"],  # Cough
            "supporting": [
                "386661006",  # Fever
                "267036007",  # Dyspnea
                "64531003",   # Nasal discharge (runny nose)
                "162397003",  # Sore throat pain
            ],
            "required_match": 1,
            "supporting_match": 2,
        },
        "conditions": [
            {
                "sctid": "233604007",
                "name": "Pneumonia",
                "name_zh": "肺炎",
                "probability": 0.5,
                "triage_level": TriageLevel.ORANGE,
                "department": "Pulmonology/Emergency",
                "icd10": "J18.9",
            },
            {
                "sctid": "54150009",
                "name": "Upper respiratory infection",
                "name_zh": "上呼吸道感染",
                "probability": 0.7,
                "triage_level": TriageLevel.GREEN,
                "department": "General Practice",
                "icd10": "J06.9",
            },
        ]
    },

    # === NEUROLOGICAL ===
    "stroke_symptoms": {
        "pattern": {
            "required": [],  # Any of the stroke symptoms
            "supporting": [
                "398979000",  # Facial droop / weakness
                "29164008",   # Speech disturbance
                "26079004",   # Tremor
                "25064002",   # Headache (severe sudden)
                "422587007",  # Nausea/vomiting
                "246636008",  # Hazy vision
            ],
            "required_match": 0,
            "supporting_match": 2,
        },
        "conditions": [
            {
                "sctid": "230690007",
                "name": "Cerebrovascular accident (Stroke)",
                "name_zh": "脑卒中",
                "probability": 0.8,
                "triage_level": TriageLevel.RED,
                "department": "Emergency/Neurology",
                "icd10": "I64",
            },
        ]
    },

    "headache_migraine": {
        "pattern": {
            "required": ["25064002"],  # Headache
            "supporting": [
                "422587007",  # Nausea
                "73905001",   # Sensitivity to light (photophobia)
                "313387002",  # Sensitivity to sound
                "246636008",  # Visual disturbance
            ],
            "required_match": 1,
            "supporting_match": 1,
        },
        "conditions": [
            {
                "sctid": "37796009",
                "name": "Migraine",
                "name_zh": "偏头痛",
                "probability": 0.6,
                "triage_level": TriageLevel.YELLOW,
                "department": "Neurology/General Practice",
                "icd10": "G43.9",
            },
        ]
    },

    # === GASTROINTESTINAL ===
    "abdominal_pain_acute": {
        "pattern": {
            "required": ["21522001"],  # Abdominal pain
            "supporting": [
                "386661006",  # Fever
                "422587007",  # Nausea
                "249497008",  # Vomiting
                "62315008",   # Diarrhea
            ],
            "required_match": 1,
            "supporting_match": 1,
        },
        "conditions": [
            {
                "sctid": "74400008",
                "name": "Appendicitis",
                "name_zh": "阑尾炎",
                "probability": 0.4,
                "triage_level": TriageLevel.ORANGE,
                "department": "Emergency/Surgery",
                "icd10": "K37",
            },
            {
                "sctid": "25374005",
                "name": "Gastroenteritis",
                "name_zh": "胃肠炎",
                "probability": 0.6,
                "triage_level": TriageLevel.YELLOW,
                "department": "Gastroenterology/General Practice",
                "icd10": "K52.9",
            },
        ]
    },
}


# ---------------------------------------------------------------------------
# Red Flag Detection Rules
# ---------------------------------------------------------------------------

RED_FLAGS = {
    # Critical symptoms that require immediate attention
    "cardiac": {
        "symptoms": ["29857009", "10000006"],  # Chest pain, radiating pain
        "modifiers": ["severe", "crushing", "压榨", "剧烈"],
        "action": "Call 120/911 immediately",
        "action_zh": "立即拨打120急救电话",
    },
    "stroke": {
        "symptoms": ["398979000", "29164008"],  # Facial weakness, speech problems
        "modifiers": ["sudden", "突然"],
        "action": "Call 120/911 - possible stroke (FAST)",
        "action_zh": "立即拨打120 - 疑似脑卒中",
    },
    "breathing": {
        "symptoms": ["267036007"],  # Dyspnea
        "modifiers": ["severe", "cannot breathe", "无法呼吸", "严重"],
        "action": "Call 120/911 immediately",
        "action_zh": "立即拨打120急救电话",
    },
    "bleeding": {
        "symptoms": ["131148009"],  # Bleeding
        "modifiers": ["severe", "uncontrolled", "大量", "止不住"],
        "action": "Apply pressure, call 120/911",
        "action_zh": "压迫止血，拨打120",
    },
    "consciousness": {
        "symptoms": ["419045004", "271594007"],  # Loss of consciousness, syncope
        "modifiers": [],  # Always urgent
        "action": "Call 120/911 immediately",
        "action_zh": "立即拨打120急救电话",
    },
}


# ---------------------------------------------------------------------------
# Triage Decision Rules (ESI-based)
# ---------------------------------------------------------------------------

TRIAGE_RULES = {
    TriageLevel.RED: {
        "description": "Immediate - Life threatening",
        "description_zh": "立即处理 - 危及生命",
        "max_wait_time": "0 minutes",
        "action": "Immediate resuscitation/intervention required",
        "action_zh": "需要立即抢救/干预",
        "examples": ["心脏骤停", "严重呼吸困难", "大出血", "意识丧失"],
    },
    TriageLevel.ORANGE: {
        "description": "Emergent - High risk",
        "description_zh": "紧急 - 高风险",
        "max_wait_time": "10 minutes",
        "action": "Rapid assessment and treatment needed",
        "action_zh": "需要快速评估和治疗",
        "examples": ["胸痛", "中风症状", "严重腹痛", "高热"],
    },
    TriageLevel.YELLOW: {
        "description": "Urgent - Needs attention soon",
        "description_zh": "较急 - 需要尽快处理",
        "max_wait_time": "30 minutes",
        "action": "Treatment within 30 minutes",
        "action_zh": "30分钟内治疗",
        "examples": ["中度疼痛", "发热", "急性感染"],
    },
    TriageLevel.GREEN: {
        "description": "Less urgent - Can wait",
        "description_zh": "普通 - 可以等待",
        "max_wait_time": "60 minutes",
        "action": "Treatment within 1-2 hours",
        "action_zh": "1-2小时内治疗",
        "examples": ["轻度感冒", "皮疹", "轻微外伤"],
    },
    TriageLevel.BLUE: {
        "description": "Non-urgent - Can be scheduled",
        "description_zh": "非急 - 可预约",
        "max_wait_time": "120+ minutes",
        "action": "Can wait for scheduled appointment",
        "action_zh": "可以预约门诊",
        "examples": ["体检", "慢性病随访", "开药"],
    },
}


# ---------------------------------------------------------------------------
# Department Routing
# ---------------------------------------------------------------------------

DEPARTMENT_ROUTING = {
    # Condition category -> Primary department
    "cardiac": ["Emergency", "Cardiology"],
    "respiratory": ["Emergency", "Pulmonology"],
    "neurological": ["Emergency", "Neurology"],
    "gastrointestinal": ["Emergency", "Gastroenterology", "Surgery"],
    "musculoskeletal": ["Orthopedics", "Emergency"],
    "dermatological": ["Dermatology"],
    "psychiatric": ["Psychiatry", "Emergency"],
    "infectious": ["Infectious Disease", "General Practice"],
    "general": ["General Practice", "Emergency"],
}


# ---------------------------------------------------------------------------
# Clinical Reasoning Engine
# ---------------------------------------------------------------------------

class ClinicalReasoningEngine:
    """
    Core clinical reasoning engine that combines:
    1. Pattern matching against known symptom-disease rules
    2. Probability calculation based on symptom combinations
    3. Red flag detection
    4. Triage level determination
    """

    def __init__(self, neo4j_enabled: bool = True):
        self.neo4j_enabled = neo4j_enabled
        self.rules = SYMPTOM_DISEASE_RULES
        self.red_flags = RED_FLAGS
        self.triage_rules = TRIAGE_RULES

    def normalize_symptoms(self, symptoms: List[str]) -> List[Dict[str, str]]:
        """
        Normalize symptom descriptions to SNOMED CT codes.
        Uses the existing neo4j_db module.

        Args:
            symptoms: List of symptom descriptions (natural language)

        Returns:
            List of {sctid, name} dictionaries
        """
        if not self.neo4j_enabled:
            return [{"sctid": s, "name": s} for s in symptoms]

        try:
            from data_pipeline.neo4j_db import snomed_search

            normalized = []
            for symptom in symptoms:
                results = snomed_search(symptom, limit=1)
                if results:
                    normalized.append({
                        "sctid": results[0]["sctid"],
                        "name": results[0]["fsn"]
                    })
                else:
                    # Keep original if not found
                    normalized.append({"sctid": symptom, "name": symptom})
            return normalized
        except Exception as e:
            logger.warning(f"SNOMED normalization failed: {e}")
            return [{"sctid": s, "name": s} for s in symptoms]

    def detect_red_flags(
        self,
        symptom_sctids: List[str],
        symptom_text: str = ""
    ) -> List[Dict[str, str]]:
        """
        Detect critical red flag symptoms that require immediate attention.

        Args:
            symptom_sctids: List of SNOMED CT codes
            symptom_text: Original symptom description for modifier detection

        Returns:
            List of detected red flags with actions
        """
        detected = []

        for flag_name, flag_config in self.red_flags.items():
            # Check if any flag symptoms are present
            symptom_match = any(
                s in symptom_sctids for s in flag_config["symptoms"]
            )

            # Check for severity modifiers in text
            modifier_match = (
                not flag_config["modifiers"]  # No modifiers = always match
                or any(m in symptom_text.lower() for m in flag_config["modifiers"])
            )

            if symptom_match and modifier_match:
                detected.append({
                    "type": flag_name,
                    "action": flag_config["action"],
                    "action_zh": flag_config["action_zh"],
                })

        return detected

    def match_patterns(
        self,
        symptom_sctids: List[str]
    ) -> List[Tuple[str, float, Dict]]:
        """
        Match symptoms against known disease patterns.

        Args:
            symptom_sctids: List of SNOMED CT codes

        Returns:
            List of (rule_name, match_score, rule_config) tuples
        """
        matches = []

        for rule_name, rule_config in self.rules.items():
            pattern = rule_config["pattern"]

            # Count required symptom matches
            required_matches = sum(
                1 for s in pattern["required"] if s in symptom_sctids
            )

            # Count supporting symptom matches
            supporting_matches = sum(
                1 for s in pattern["supporting"] if s in symptom_sctids
            )

            # Check if pattern criteria met
            required_ok = required_matches >= pattern["required_match"]
            supporting_ok = supporting_matches >= pattern["supporting_match"]

            if required_ok and supporting_ok:
                # Calculate match score
                total_possible = len(pattern["required"]) + len(pattern["supporting"])
                total_matched = required_matches + supporting_matches
                match_score = total_matched / max(total_possible, 1)

                matches.append((rule_name, match_score, rule_config))

        # Sort by match score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def calculate_probabilities(
        self,
        matched_rules: List[Tuple[str, float, Dict]],
        symptom_sctids: List[str]
    ) -> List[DiseaseCandidate]:
        """
        Calculate disease probabilities based on matched patterns.

        Args:
            matched_rules: Output from match_patterns()
            symptom_sctids: List of SNOMED CT codes

        Returns:
            List of DiseaseCandidate objects sorted by probability
        """
        candidates = []

        for rule_name, match_score, rule_config in matched_rules:
            for condition in rule_config["conditions"]:
                # Adjust probability based on match score
                adjusted_prob = condition["probability"] * match_score

                # Find which symptoms matched as evidence
                pattern = rule_config["pattern"]
                evidence = [
                    s for s in symptom_sctids
                    if s in pattern["required"] or s in pattern["supporting"]
                ]

                candidate = DiseaseCandidate(
                    sctid=condition["sctid"],
                    name=condition["name"],
                    probability=round(adjusted_prob, 2),
                    evidence=evidence,
                    triage_level=condition["triage_level"],
                    department=condition["department"],
                    icd10_code=condition.get("icd10"),
                )
                candidates.append(candidate)

        # Sort by probability descending
        candidates.sort(key=lambda x: x.probability, reverse=True)

        # Remove duplicates (keep highest probability)
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c.sctid not in seen:
                seen.add(c.sctid)
                unique_candidates.append(c)

        return unique_candidates

    def determine_triage_level(
        self,
        candidates: List[DiseaseCandidate],
        red_flags: List[Dict]
    ) -> TriageLevel:
        """
        Determine overall triage level based on candidates and red flags.

        Args:
            candidates: List of disease candidates
            red_flags: Detected red flags

        Returns:
            Most urgent triage level
        """
        # Red flags always escalate to RED or ORANGE
        if red_flags:
            return TriageLevel.RED

        if not candidates:
            return TriageLevel.GREEN  # Default if no matches

        # Use highest priority (lowest value) triage level
        return min(c.triage_level for c in candidates)

    def get_recommended_action(
        self,
        triage_level: TriageLevel,
        red_flags: List[Dict],
        language: str = "en"
    ) -> str:
        """
        Get recommended action based on triage level.

        Args:
            triage_level: Determined triage level
            red_flags: Detected red flags
            language: "en" or "zh"

        Returns:
            Recommended action string
        """
        # If red flags, use specific action
        if red_flags:
            if language == "zh":
                return red_flags[0]["action_zh"]
            return red_flags[0]["action"]

        # Otherwise use triage rule action
        rule = self.triage_rules[triage_level]
        if language == "zh":
            return rule["action_zh"]
        return rule["action"]

    def reason(
        self,
        symptoms: List[str],
        symptom_text: str = "",
        language: str = "zh"
    ) -> TriageResult:
        """
        Main reasoning function - takes symptoms and returns triage result.

        Args:
            symptoms: List of symptom descriptions or SNOMED codes
            symptom_text: Original patient description (for red flag detection)
            language: Output language ("en" or "zh")

        Returns:
            TriageResult with complete triage decision
        """
        # Step 1: Normalize symptoms to SNOMED CT
        normalized = self.normalize_symptoms(symptoms)
        symptom_sctids = [s["sctid"] for s in normalized]

        logger.info(f"Normalized symptoms: {normalized}")

        # Step 2: Detect red flags
        red_flags = self.detect_red_flags(symptom_sctids, symptom_text)

        if red_flags:
            logger.warning(f"Red flags detected: {red_flags}")

        # Step 3: Match against patterns
        matched_rules = self.match_patterns(symptom_sctids)

        logger.info(f"Matched {len(matched_rules)} rules")

        # Step 4: Calculate disease probabilities
        candidates = self.calculate_probabilities(matched_rules, symptom_sctids)

        # Step 5: Determine triage level
        triage_level = self.determine_triage_level(candidates, red_flags)

        # Step 6: Map to urgency level
        urgency_map = {
            TriageLevel.RED: UrgencyLevel.EMERGENCY,
            TriageLevel.ORANGE: UrgencyLevel.URGENT,
            TriageLevel.YELLOW: UrgencyLevel.SOON,
            TriageLevel.GREEN: UrgencyLevel.ROUTINE,
            TriageLevel.BLUE: UrgencyLevel.ROUTINE,
        }
        urgency = urgency_map[triage_level]

        # Step 7: Get recommended action
        action = self.get_recommended_action(triage_level, red_flags, language)

        # Step 8: Determine department
        if candidates:
            department = candidates[0].department
        elif red_flags:
            department = "Emergency"
        else:
            department = "General Practice"

        # Step 9: Calculate confidence
        if candidates:
            confidence = candidates[0].probability
        elif red_flags:
            confidence = 0.9  # High confidence for red flags
        else:
            confidence = 0.3  # Low confidence if no matches

        return TriageResult(
            urgency=urgency,
            triage_level=triage_level,
            primary_condition=candidates[0] if candidates else None,
            differential_diagnosis=candidates[1:4],  # Top 3 alternatives
            recommended_department=department,
            recommended_action=action,
            red_flags_detected=[rf["type"] for rf in red_flags],
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def triage_patient(
    symptoms: List[str],
    symptom_text: str = "",
    language: str = "zh"
) -> Dict[str, Any]:
    """
    Convenience function for patient triage.

    Args:
        symptoms: List of symptom descriptions
        symptom_text: Original patient text
        language: Output language

    Returns:
        Dictionary with triage results
    """
    engine = ClinicalReasoningEngine(neo4j_enabled=True)
    result = engine.reason(symptoms, symptom_text, language)

    return {
        "urgency": result.urgency.value,
        "triage_level": result.triage_level.value,
        "triage_description": TRIAGE_RULES[result.triage_level]["description_zh"],
        "primary_condition": {
            "sctid": result.primary_condition.sctid,
            "name": result.primary_condition.name,
            "probability": result.primary_condition.probability,
            "icd10": result.primary_condition.icd10_code,
        } if result.primary_condition else None,
        "differential_diagnosis": [
            {
                "sctid": c.sctid,
                "name": c.name,
                "probability": c.probability,
            }
            for c in result.differential_diagnosis
        ],
        "department": result.recommended_department,
        "action": result.recommended_action,
        "red_flags": result.red_flags_detected,
        "confidence": result.confidence,
    }


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test cases
    print("=" * 60)
    print("Testing Clinical Reasoning Engine")
    print("=" * 60)

    engine = ClinicalReasoningEngine(neo4j_enabled=False)  # Disable Neo4j for testing

    # Test Case 1: Cardiac emergency
    print("\n--- Test Case 1: Cardiac Emergency ---")
    symptoms1 = ["29857009", "10000006", "415690000"]  # Chest pain, radiating, sweating
    result1 = engine.reason(symptoms1, "胸口剧烈疼痛，向左肩放射，出冷汗")
    print(f"Urgency: {result1.urgency.value}")
    print(f"Triage Level: {result1.triage_level.name}")
    print(f"Primary Condition: {result1.primary_condition.name if result1.primary_condition else 'None'}")
    print(f"Action: {result1.recommended_action}")
    print(f"Red Flags: {result1.red_flags_detected}")

    # Test Case 2: Respiratory infection
    print("\n--- Test Case 2: Respiratory Infection ---")
    symptoms2 = ["49727002", "386661006", "64531003"]  # Cough, fever, runny nose
    result2 = engine.reason(symptoms2, "咳嗽发烧流鼻涕")
    print(f"Urgency: {result2.urgency.value}")
    print(f"Triage Level: {result2.triage_level.name}")
    print(f"Primary Condition: {result2.primary_condition.name if result2.primary_condition else 'None'}")
    print(f"Action: {result2.recommended_action}")

    # Test Case 3: Using convenience function
    print("\n--- Test Case 3: Convenience Function ---")
    result3 = triage_patient(
        symptoms=["headache", "nausea", "sensitivity to light"],
        symptom_text="剧烈头痛，恶心，怕光",
        language="zh"
    )
    print(f"Result: {result3}")
