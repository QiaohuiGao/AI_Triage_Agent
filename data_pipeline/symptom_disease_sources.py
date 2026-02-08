"""
Symptom-Disease Knowledge Sources
=================================

This module provides multiple approaches to obtain symptom-disease relationships:

1. SNOMED CT Implicit Relationships - Extract from existing SNOMED structure
2. LLM-based Extraction - Use GPT-4 with medical prompts + validation
3. Medical Guidelines Import - Parse structured guidelines
4. UMLS Integration - Use UMLS relationships (requires license)
5. Human Expert Curation - Interface for medical expert review

Architecture:
    Multiple Sources → Validation Layer → Confidence Scoring → Final KB

IMPORTANT: This is a framework for obtaining relationships from authoritative
sources, NOT hardcoded rules. All relationships should be validated by
medical professionals before use in production.
"""

import os
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class SourceType(Enum):
    """Source of the symptom-disease relationship"""
    SNOMED_INFERRED = "snomed_inferred"       # Inferred from SNOMED structure
    UMLS = "umls"                              # From UMLS
    MEDICAL_GUIDELINE = "medical_guideline"   # From clinical guidelines
    LLM_EXTRACTED = "llm_extracted"           # Extracted by LLM from literature
    EXPERT_CURATED = "expert_curated"         # Validated by medical expert
    CLINICAL_DATA = "clinical_data"           # Learned from clinical data


class ValidationStatus(Enum):
    """Validation status of a relationship"""
    PENDING = "pending"           # Not yet validated
    VALIDATED = "validated"       # Validated by expert
    REJECTED = "rejected"         # Rejected by expert
    AUTO_VALIDATED = "auto"       # Auto-validated (high confidence source)


@dataclass
class SymptomDiseaseRelation:
    """A relationship between a symptom and a disease"""
    symptom_sctid: str
    symptom_name: str
    disease_sctid: str
    disease_name: str
    probability: float              # 0.0 to 1.0
    evidence_strength: str          # "strong", "moderate", "weak"
    source: SourceType
    source_reference: str           # Citation or source URL
    validation_status: ValidationStatus
    validated_by: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Source 1: Extract from SNOMED CT Structure
# ---------------------------------------------------------------------------

class SNOMEDRelationshipExtractor:
    """
    Extract implicit symptom-disease relationships from SNOMED CT.

    SNOMED CT has concepts with:
    - Finding site (body location)
    - Associated morphology (type of abnormality)
    - Clinical finding hierarchy

    We can infer that symptoms and diseases affecting the same body
    structure may be related.
    """

    def __init__(self):
        from data_pipeline.neo4j_db import neo4j_conn
        self.neo4j_conn = neo4j_conn

    def find_diseases_by_finding_site(
        self,
        body_structure_sctid: str
    ) -> List[Dict[str, Any]]:
        """
        Find diseases that affect a specific body structure.

        Example: body_structure = "80891009" (Heart structure)
                 Returns diseases like MI, Angina, Heart failure
        """
        query = """
        // Find diseases that have this body structure as finding site
        MATCH (disease:ObjectConcept)-[:HAS_ROLE_GROUP]->(rg:RoleGroup)-[r]->(site:ObjectConcept)
        WHERE site.sctid = $body_sctid
        AND type(r) CONTAINS 'Finding_site'
        AND disease.active = '1'
        // Check if it's a disease (under Clinical finding or Disorder)
        MATCH (disease)-[:ISA*1..5]->(parent:ObjectConcept)
        WHERE parent.sctid IN ['404684003', '64572001']  // Clinical finding, Disease
        RETURN DISTINCT disease.sctid AS sctid, disease.FSN AS name
        LIMIT 50
        """

        with self.neo4j_conn() as session:
            result = session.run(query, body_sctid=body_structure_sctid)
            return [{"sctid": r["sctid"], "name": r["name"]} for r in result]

    def find_symptoms_for_body_structure(
        self,
        body_structure_sctid: str
    ) -> List[Dict[str, Any]]:
        """
        Find symptoms that occur in a specific body structure.

        Example: body_structure = "80891009" (Heart structure)
                 Returns symptoms like chest pain, palpitations
        """
        query = """
        // Find symptoms related to this body structure
        MATCH (symptom:ObjectConcept)-[:ISA*1..5]->(parent:ObjectConcept {sctid: '404684003'})
        WHERE symptom.FSN CONTAINS 'finding' OR symptom.FSN CONTAINS 'symptom'
        AND symptom.active = '1'
        // Check if symptom mentions the body structure
        MATCH (symptom)-[:HAS_ROLE_GROUP]->(rg:RoleGroup)-[r]->(site:ObjectConcept)
        WHERE site.sctid = $body_sctid
        RETURN DISTINCT symptom.sctid AS sctid, symptom.FSN AS name
        LIMIT 50
        """

        with self.neo4j_conn() as session:
            result = session.run(query, body_sctid=body_structure_sctid)
            return [{"sctid": r["sctid"], "name": r["name"]} for r in result]

    def infer_symptom_disease_by_site(
        self,
        body_structure_sctid: str,
        body_structure_name: str
    ) -> List[SymptomDiseaseRelation]:
        """
        Infer symptom-disease relationships based on shared body structure.

        This creates weak relationships that need expert validation.
        """
        symptoms = self.find_symptoms_for_body_structure(body_structure_sctid)
        diseases = self.find_diseases_by_finding_site(body_structure_sctid)

        relations = []
        for symptom in symptoms:
            for disease in diseases:
                relation = SymptomDiseaseRelation(
                    symptom_sctid=symptom["sctid"],
                    symptom_name=symptom["name"],
                    disease_sctid=disease["sctid"],
                    disease_name=disease["name"],
                    probability=0.1,  # Low default - needs validation
                    evidence_strength="weak",
                    source=SourceType.SNOMED_INFERRED,
                    source_reference=f"SNOMED CT: shared finding site {body_structure_name}",
                    validation_status=ValidationStatus.PENDING,
                    notes="Inferred from shared body structure - needs clinical validation"
                )
                relations.append(relation)

        return relations


# ---------------------------------------------------------------------------
# Source 2: LLM-based Extraction from Medical Literature
# ---------------------------------------------------------------------------

class LLMKnowledgeExtractor:
    """
    Use LLM to extract symptom-disease relationships from medical text.

    This approach:
    1. Takes medical text (guideline, textbook excerpt)
    2. Prompts LLM to extract structured relationships
    3. Validates against SNOMED CT
    4. Flags for human review
    """

    def __init__(self):
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")

    def extract_from_text(
        self,
        medical_text: str,
        source_reference: str
    ) -> List[SymptomDiseaseRelation]:
        """
        Extract symptom-disease relationships from medical text.

        Args:
            medical_text: Text from medical guideline/textbook
            source_reference: Citation for the text

        Returns:
            List of extracted relationships (needs validation)
        """
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        prompt = f"""You are a medical knowledge extraction system.

Extract symptom-disease relationships from the following medical text.

For each relationship, provide:
1. symptom: The symptom/clinical finding
2. disease: The disease/condition
3. probability: Estimated probability (0.0-1.0) that this symptom indicates this disease
4. evidence_strength: "strong", "moderate", or "weak"

Return as JSON array:
[
  {{
    "symptom": "chest pain",
    "disease": "myocardial infarction",
    "probability": 0.3,
    "evidence_strength": "strong"
  }}
]

Medical text:
{medical_text}

Extract ALL symptom-disease relationships mentioned or implied.
Only include relationships where there is genuine clinical association.
"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistency
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            # Handle both array and object with array
            if isinstance(data, dict):
                relations_data = data.get("relationships", data.get("relations", []))
            else:
                relations_data = data

            relations = []
            for item in relations_data:
                # Normalize to SNOMED CT (would need actual implementation)
                relation = SymptomDiseaseRelation(
                    symptom_sctid="",  # To be resolved
                    symptom_name=item.get("symptom", ""),
                    disease_sctid="",  # To be resolved
                    disease_name=item.get("disease", ""),
                    probability=float(item.get("probability", 0.1)),
                    evidence_strength=item.get("evidence_strength", "weak"),
                    source=SourceType.LLM_EXTRACTED,
                    source_reference=source_reference,
                    validation_status=ValidationStatus.PENDING,
                    notes="Extracted by LLM - requires expert validation"
                )
                relations.append(relation)

            return relations

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []

    def resolve_to_snomed(
        self,
        relation: SymptomDiseaseRelation
    ) -> Optional[SymptomDiseaseRelation]:
        """
        Resolve symptom and disease names to SNOMED CT codes.
        """
        try:
            from data_pipeline.neo4j_db import snomed_search

            # Search for symptom
            symptom_results = snomed_search(relation.symptom_name, limit=1)
            if symptom_results:
                relation.symptom_sctid = symptom_results[0]["sctid"]
                relation.symptom_name = symptom_results[0]["fsn"]

            # Search for disease
            disease_results = snomed_search(relation.disease_name, limit=1)
            if disease_results:
                relation.disease_sctid = disease_results[0]["sctid"]
                relation.disease_name = disease_results[0]["fsn"]

            if relation.symptom_sctid and relation.disease_sctid:
                return relation

        except Exception as e:
            logger.warning(f"SNOMED resolution failed: {e}")

        return None


# ---------------------------------------------------------------------------
# Source 3: Medical Guidelines Parser
# ---------------------------------------------------------------------------

class GuidelineParser:
    """
    Parse structured medical guidelines (e.g., NICE, AHA, ESC).

    Many guidelines have structured sections like:
    - Clinical Presentation / Symptoms
    - Differential Diagnosis
    - Red Flags

    This parser extracts these structured relationships.
    """

    def parse_differential_diagnosis_table(
        self,
        table_text: str,
        guideline_name: str
    ) -> List[SymptomDiseaseRelation]:
        """
        Parse a differential diagnosis table from a guideline.

        Example table format:
        | Symptom | Possible Conditions | Likelihood |
        | Chest pain, sudden | MI, PE, Aortic dissection | High |
        """
        # This would need actual implementation based on guideline format
        # For now, return empty - would integrate with specific parsers
        logger.info(f"Parsing guideline: {guideline_name}")
        return []


# ---------------------------------------------------------------------------
# Knowledge Validation and Aggregation
# ---------------------------------------------------------------------------

class KnowledgeValidator:
    """
    Validates and aggregates symptom-disease relationships from multiple sources.

    Validation strategies:
    1. Cross-source agreement - If multiple sources agree, higher confidence
    2. SNOMED CT consistency - Check if relationship makes semantic sense
    3. Expert review queue - Flag uncertain relationships for review
    """

    def __init__(self):
        self.relations: List[SymptomDiseaseRelation] = []

    def add_relations(self, relations: List[SymptomDiseaseRelation]):
        """Add relations from a source."""
        self.relations.extend(relations)

    def calculate_confidence(
        self,
        symptom_sctid: str,
        disease_sctid: str
    ) -> Tuple[float, List[SymptomDiseaseRelation]]:
        """
        Calculate confidence for a symptom-disease pair based on sources.

        Returns:
            (confidence_score, supporting_relations)
        """
        # Find all relations for this pair
        matching = [
            r for r in self.relations
            if r.symptom_sctid == symptom_sctid
            and r.disease_sctid == disease_sctid
        ]

        if not matching:
            return 0.0, []

        # Weight by source reliability
        source_weights = {
            SourceType.EXPERT_CURATED: 1.0,
            SourceType.MEDICAL_GUIDELINE: 0.9,
            SourceType.UMLS: 0.8,
            SourceType.CLINICAL_DATA: 0.7,
            SourceType.LLM_EXTRACTED: 0.5,
            SourceType.SNOMED_INFERRED: 0.3,
        }

        # Calculate weighted average
        total_weight = 0.0
        weighted_prob = 0.0

        for r in matching:
            weight = source_weights.get(r.source, 0.5)
            weighted_prob += r.probability * weight
            total_weight += weight

        if total_weight > 0:
            avg_probability = weighted_prob / total_weight

            # Boost for multiple sources
            source_count = len(set(r.source for r in matching))
            confidence_boost = min(source_count * 0.1, 0.3)

            return min(avg_probability + confidence_boost, 1.0), matching

        return 0.0, []

    def get_validated_relations(
        self,
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Get all validated relations above confidence threshold.
        """
        # Group by symptom-disease pair
        pairs = {}
        for r in self.relations:
            key = (r.symptom_sctid, r.disease_sctid)
            if key not in pairs:
                pairs[key] = []
            pairs[key].append(r)

        # Calculate confidence for each pair
        validated = []
        for (symptom, disease), relations in pairs.items():
            if not symptom or not disease:
                continue

            confidence, sources = self.calculate_confidence(symptom, disease)
            if confidence >= min_confidence:
                validated.append({
                    "symptom_sctid": symptom,
                    "symptom_name": relations[0].symptom_name,
                    "disease_sctid": disease,
                    "disease_name": relations[0].disease_name,
                    "confidence": confidence,
                    "source_count": len(sources),
                    "sources": [r.source.value for r in sources],
                    "needs_review": confidence < 0.7,
                })

        return sorted(validated, key=lambda x: x["confidence"], reverse=True)

    def export_for_review(self, output_path: str):
        """
        Export pending relations for expert review.
        """
        pending = [
            r for r in self.relations
            if r.validation_status == ValidationStatus.PENDING
        ]

        review_data = []
        for r in pending:
            review_data.append({
                "symptom_sctid": r.symptom_sctid,
                "symptom_name": r.symptom_name,
                "disease_sctid": r.disease_sctid,
                "disease_name": r.disease_name,
                "probability": r.probability,
                "source": r.source.value,
                "source_reference": r.source_reference,
                "notes": r.notes,
                # For reviewer to fill:
                "validated": None,  # True/False
                "adjusted_probability": None,
                "reviewer_notes": "",
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(review_data)} relations for review to {output_path}")


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

class SymptomDiseaseKnowledgePipeline:
    """
    Main pipeline for building symptom-disease knowledge base.

    Usage:
        pipeline = SymptomDiseaseKnowledgePipeline()
        pipeline.extract_from_snomed()
        pipeline.extract_from_guidelines(guideline_texts)
        pipeline.validate_and_export()
    """

    def __init__(self):
        self.validator = KnowledgeValidator()
        self.snomed_extractor = None
        self.llm_extractor = None

    def extract_from_snomed(self, body_structures: List[Tuple[str, str]] = None):
        """
        Extract relationships from SNOMED CT structure.

        Args:
            body_structures: List of (sctid, name) for body structures to analyze
        """
        if self.snomed_extractor is None:
            self.snomed_extractor = SNOMEDRelationshipExtractor()

        if body_structures is None:
            # Default important body structures
            body_structures = [
                ("80891009", "Heart structure"),
                ("39607008", "Lung structure"),
                ("69536005", "Head structure"),
                ("113345001", "Chest structure"),
                ("818983003", "Abdomen structure"),
            ]

        for sctid, name in body_structures:
            logger.info(f"Extracting relationships for: {name}")
            relations = self.snomed_extractor.infer_symptom_disease_by_site(sctid, name)
            self.validator.add_relations(relations)
            logger.info(f"  Found {len(relations)} potential relationships")

    def extract_from_text(self, medical_text: str, source_reference: str):
        """
        Extract relationships from medical text using LLM.
        """
        if self.llm_extractor is None:
            self.llm_extractor = LLMKnowledgeExtractor()

        relations = self.llm_extractor.extract_from_text(medical_text, source_reference)

        # Resolve to SNOMED CT
        resolved = []
        for r in relations:
            resolved_r = self.llm_extractor.resolve_to_snomed(r)
            if resolved_r:
                resolved.append(resolved_r)

        self.validator.add_relations(resolved)
        logger.info(f"Extracted {len(resolved)} relationships from text")

    def validate_and_export(self, output_dir: str = "./knowledge_export"):
        """
        Validate relationships and export for review.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Get validated relations
        validated = self.validator.get_validated_relations(min_confidence=0.3)

        # Export validated
        with open(f"{output_dir}/validated_relations.json", 'w', encoding='utf-8') as f:
            json.dump(validated, f, indent=2, ensure_ascii=False)

        # Export for review
        self.validator.export_for_review(f"{output_dir}/pending_review.json")

        logger.info(f"Exported {len(validated)} validated relations")
        logger.info(f"Check {output_dir}/pending_review.json for expert review")

        return validated


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Symptom-Disease Knowledge Pipeline")
    print("=" * 60)

    # Example: Extract from medical text
    sample_text = """
    Acute Myocardial Infarction (Heart Attack)

    Clinical Presentation:
    - Chest pain: Typically described as pressure, squeezing, or heaviness.
      Present in approximately 70-80% of patients.
    - Radiation: Pain may radiate to the left arm, jaw, or back (40-50% of cases)
    - Diaphoresis (sweating): Present in 50-60% of cases
    - Dyspnea (shortness of breath): Common accompanying symptom (40-50%)
    - Nausea/vomiting: May occur, especially in inferior MI (30-40%)

    Red Flags:
    - Sudden onset of crushing chest pain
    - Pain lasting >20 minutes
    - Associated syncope or near-syncope
    - Severe dyspnea

    Differential Diagnosis:
    - Unstable angina: Similar presentation but without myocardial necrosis
    - Pulmonary embolism: May present with chest pain and dyspnea
    - Aortic dissection: Severe tearing chest pain, may radiate to back
    - Panic attack: Chest discomfort with anxiety, palpitations
    """

    print("\nNote: This is a demonstration of the extraction pipeline.")
    print("Real deployment requires:")
    print("1. Medical professional review of extracted relationships")
    print("2. Integration with authoritative sources (UMLS, guidelines)")
    print("3. Continuous validation and updates")

    # To actually run:
    # pipeline = SymptomDiseaseKnowledgePipeline()
    # pipeline.extract_from_text(sample_text, "AHA Guidelines 2023")
    # pipeline.validate_and_export()
