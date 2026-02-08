"""
Build Multi-Level Vector Stores for Triage Agent
=================================================

Based on the design document, we need three vector stores:

1. Symptom Vector Store (symptom-level)
   - Short clinical definitions
   - Symptom descriptions and synonyms
   - Source: SNOMED CT descriptions + medical dictionaries

2. Condition Vector Store (condition-level)
   - Detailed disease guidelines
   - Symptom-disease relationships
   - Differential diagnosis info
   - Source: Clinical guidelines, UMLS, medical textbooks

3. Care-Path Vector Store (care-path-level)
   - Hospital department mappings
   - Triage urgency rules
   - Routing logic
   - Source: Hospital KB, ESI guidelines, clinical protocols

Usage:
    python build_vector_stores.py --store symptom
    python build_vector_stores.py --store condition
    python build_vector_stores.py --store carepath
    python build_vector_stores.py --all
"""

import os
import json
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INDEX_DIR = Path(os.getenv("INDEX_DIR", "./index"))
INDEX_DIR.mkdir(exist_ok=True)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536  # For OpenAI text-embedding-3-small


@dataclass
class Document:
    """A document to be indexed"""
    id: str
    text: str
    metadata: Dict[str, Any]
    level: str  # "symptom", "condition", or "carepath"


# ---------------------------------------------------------------------------
# Embedding Functions
# ---------------------------------------------------------------------------

def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a list of texts using OpenAI."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    return [item.embedding for item in response.data]


def batch_embed(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Embed texts in batches to avoid API limits."""
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        logger.info(f"Embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
        embeddings = get_embeddings(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


# ---------------------------------------------------------------------------
# 1. Symptom Vector Store Builder
# ---------------------------------------------------------------------------

class SymptomStoreBuilder:
    """
    Build symptom-level vector store from SNOMED CT.

    Content:
    - Symptom names and synonyms
    - Short clinical definitions
    - SNOMED CT codes for grounding
    """

    def __init__(self):
        self.documents: List[Document] = []

    def load_from_snomed(self, limit: int = 5000) -> int:
        """
        Load symptom descriptions from Neo4j SNOMED CT.
        Focuses on Clinical Findings (symptoms, signs).
        """
        try:
            from data_pipeline.neo4j_db import neo4j_conn
        except ImportError:
            logger.error("neo4j_db module not found")
            return 0

        # Query for clinical findings (symptoms)
        query = """
        MATCH (c:ObjectConcept)-[:ISA*1..5]->(parent:ObjectConcept)
        WHERE parent.sctid = '404684003'  // Clinical finding
        AND c.active = '1'
        WITH c LIMIT $limit
        OPTIONAL MATCH (c)-[:HAS_DESCRIPTION]->(d:Description)
        WHERE d.active = '1'
        RETURN c.sctid AS sctid,
               c.FSN AS fsn,
               collect(DISTINCT d.term) AS synonyms
        """

        with neo4j_conn() as session:
            result = session.run(query, limit=limit)

            for record in result:
                sctid = record["sctid"]
                fsn = record["fsn"]
                synonyms = record["synonyms"] or []

                # Create document text
                text = f"Symptom: {fsn}\n"
                if synonyms:
                    text += f"Also known as: {', '.join(synonyms[:5])}\n"
                text += f"SNOMED CT Code: {sctid}"

                doc = Document(
                    id=f"symptom_{sctid}",
                    text=text,
                    metadata={
                        "sctid": sctid,
                        "fsn": fsn,
                        "synonyms": synonyms[:10],
                        "type": "symptom"
                    },
                    level="symptom"
                )
                self.documents.append(doc)

        logger.info(f"Loaded {len(self.documents)} symptom documents from SNOMED CT")
        return len(self.documents)

    def load_from_file(self, filepath: str) -> int:
        """Load additional symptom definitions from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            doc = Document(
                id=f"symptom_{item.get('id', len(self.documents))}",
                text=item["text"],
                metadata=item.get("metadata", {}),
                level="symptom"
            )
            self.documents.append(doc)

        return len(data)

    def build_index(self, output_name: str = "symptom_store"):
        """Build FAISS index from documents."""
        import faiss
        import numpy as np

        if not self.documents:
            logger.error("No documents to index")
            return

        # Get embeddings
        texts = [doc.text for doc in self.documents]
        embeddings = batch_embed(texts)

        # Create FAISS index
        embeddings_np = np.array(embeddings).astype('float32')
        index = faiss.IndexFlatIP(EMBEDDING_DIM)  # Inner product for cosine similarity

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings_np)
        index.add(embeddings_np)

        # Save index
        index_path = INDEX_DIR / f"{output_name}.index"
        faiss.write_index(index, str(index_path))

        # Save document IDs and metadata
        ids_path = INDEX_DIR / f"{output_name}_docs.json"
        docs_data = [
            {
                "id": doc.id,
                "text": doc.text,
                "metadata": doc.metadata
            }
            for doc in self.documents
        ]
        with open(ids_path, 'w', encoding='utf-8') as f:
            json.dump(docs_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Built symptom index with {len(self.documents)} documents")
        logger.info(f"Saved to: {index_path}")


# ---------------------------------------------------------------------------
# 2. Condition Vector Store Builder
# ---------------------------------------------------------------------------

class ConditionStoreBuilder:
    """
    Build condition-level vector store.

    Content:
    - Disease descriptions and symptoms
    - Differential diagnosis information
    - Clinical guidelines excerpts
    """

    def __init__(self):
        self.documents: List[Document] = []

    def load_from_snomed_diseases(self, limit: int = 3000) -> int:
        """Load disease concepts from SNOMED CT."""
        try:
            from data_pipeline.neo4j_db import neo4j_conn
        except ImportError:
            logger.error("neo4j_db module not found")
            return 0

        # Query for disorders/diseases
        query = """
        MATCH (c:ObjectConcept)-[:ISA*1..5]->(parent:ObjectConcept)
        WHERE parent.sctid = '64572001'  // Disease (disorder)
        AND c.active = '1'
        WITH c LIMIT $limit
        OPTIONAL MATCH (c)-[:HAS_DESCRIPTION]->(d:Description)
        WHERE d.active = '1'
        // Get related symptoms via MAY_INDICATE (if exists)
        OPTIONAL MATCH (symptom:ObjectConcept)-[r:MAY_INDICATE]->(c)
        RETURN c.sctid AS sctid,
               c.FSN AS fsn,
               collect(DISTINCT d.term) AS descriptions,
               collect(DISTINCT {symptom: symptom.FSN, prob: r.probability}) AS symptoms
        """

        with neo4j_conn() as session:
            result = session.run(query, limit=limit)

            for record in result:
                sctid = record["sctid"]
                fsn = record["fsn"]
                descriptions = record["descriptions"] or []
                symptoms = record["symptoms"] or []

                # Create document text
                text = f"Condition: {fsn}\n"
                text += f"SNOMED CT Code: {sctid}\n"

                if descriptions:
                    text += f"Alternative names: {', '.join(descriptions[:5])}\n"

                if symptoms and symptoms[0].get("symptom"):
                    symptom_list = [s["symptom"] for s in symptoms if s.get("symptom")]
                    text += f"Associated symptoms: {', '.join(symptom_list[:10])}\n"

                doc = Document(
                    id=f"condition_{sctid}",
                    text=text,
                    metadata={
                        "sctid": sctid,
                        "fsn": fsn,
                        "type": "condition"
                    },
                    level="condition"
                )
                self.documents.append(doc)

        logger.info(f"Loaded {len(self.documents)} condition documents")
        return len(self.documents)

    def load_from_guidelines(self, guidelines_dir: str) -> int:
        """
        Load clinical guidelines from JSON files.

        Expected format:
        {
            "condition": "Myocardial Infarction",
            "sctid": "22298006",
            "icd10": "I21.9",
            "symptoms": ["chest pain", "shortness of breath", ...],
            "red_flags": ["crushing chest pain", "radiating to arm", ...],
            "differential_diagnosis": ["angina", "GERD", ...],
            "urgency": "emergency",
            "department": "Cardiology/Emergency",
            "guidelines_text": "..."
        }
        """
        guidelines_path = Path(guidelines_dir)
        if not guidelines_path.exists():
            logger.warning(f"Guidelines directory not found: {guidelines_dir}")
            return 0

        count = 0
        for file in guidelines_path.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both single object and array
            items = data if isinstance(data, list) else [data]

            for item in items:
                text = f"Condition: {item.get('condition', 'Unknown')}\n"

                if item.get("symptoms"):
                    text += f"Symptoms: {', '.join(item['symptoms'])}\n"

                if item.get("red_flags"):
                    text += f"Red flags: {', '.join(item['red_flags'])}\n"

                if item.get("differential_diagnosis"):
                    text += f"Differential diagnosis: {', '.join(item['differential_diagnosis'])}\n"

                if item.get("guidelines_text"):
                    text += f"\n{item['guidelines_text']}\n"

                doc = Document(
                    id=f"guideline_{item.get('sctid', count)}",
                    text=text,
                    metadata={
                        "sctid": item.get("sctid"),
                        "icd10": item.get("icd10"),
                        "condition": item.get("condition"),
                        "urgency": item.get("urgency"),
                        "department": item.get("department"),
                        "type": "guideline"
                    },
                    level="condition"
                )
                self.documents.append(doc)
                count += 1

        logger.info(f"Loaded {count} guideline documents")
        return count

    def build_index(self, output_name: str = "condition_store"):
        """Build FAISS index from documents."""
        import faiss
        import numpy as np

        if not self.documents:
            logger.error("No documents to index")
            return

        texts = [doc.text for doc in self.documents]
        embeddings = batch_embed(texts)

        embeddings_np = np.array(embeddings).astype('float32')
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        faiss.normalize_L2(embeddings_np)
        index.add(embeddings_np)

        index_path = INDEX_DIR / f"{output_name}.index"
        faiss.write_index(index, str(index_path))

        ids_path = INDEX_DIR / f"{output_name}_docs.json"
        docs_data = [
            {"id": doc.id, "text": doc.text, "metadata": doc.metadata}
            for doc in self.documents
        ]
        with open(ids_path, 'w', encoding='utf-8') as f:
            json.dump(docs_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Built condition index with {len(self.documents)} documents")


# ---------------------------------------------------------------------------
# 3. Care-Path Vector Store Builder
# ---------------------------------------------------------------------------

class CarePathStoreBuilder:
    """
    Build care-path-level vector store.

    Content:
    - Department descriptions and specialties
    - Condition-to-department routing rules
    - Urgency/triage guidelines
    """

    def __init__(self):
        self.documents: List[Document] = []

    def load_triage_rules(self) -> int:
        """Load ESI-based triage rules."""

        # ESI (Emergency Severity Index) levels
        triage_rules = [
            {
                "level": 1,
                "name": "Resuscitation",
                "description": "Immediate life-saving intervention required",
                "examples": [
                    "Cardiac arrest",
                    "Respiratory arrest",
                    "Severe anaphylaxis",
                    "Major trauma with active bleeding"
                ],
                "action": "Immediate resuscitation, multiple resources"
            },
            {
                "level": 2,
                "name": "Emergent",
                "description": "High risk situation, confused/lethargic/disoriented, or severe pain",
                "examples": [
                    "Chest pain with cardiac risk factors",
                    "Stroke symptoms (FAST positive)",
                    "Severe asthma attack",
                    "Active GI bleeding"
                ],
                "action": "Immediate bedside evaluation, should not wait"
            },
            {
                "level": 3,
                "name": "Urgent",
                "description": "Requires multiple resources but stable vital signs",
                "examples": [
                    "Abdominal pain requiring workup",
                    "Moderate asthma",
                    "Dehydration requiring IV fluids",
                    "Complex laceration"
                ],
                "action": "Can wait up to 30 minutes, needs evaluation"
            },
            {
                "level": 4,
                "name": "Less Urgent",
                "description": "Requires one resource, non-urgent",
                "examples": [
                    "Simple laceration",
                    "Urinary tract infection",
                    "Minor allergic reaction",
                    "Prescription refill with symptoms"
                ],
                "action": "Can wait 1-2 hours"
            },
            {
                "level": 5,
                "name": "Non-Urgent",
                "description": "Requires no resources, could be handled in clinic",
                "examples": [
                    "Chronic pain refill",
                    "Minor cold symptoms",
                    "Rash without systemic symptoms",
                    "Suture removal"
                ],
                "action": "Can wait, consider clinic referral"
            }
        ]

        for rule in triage_rules:
            text = f"Triage Level {rule['level']}: {rule['name']}\n"
            text += f"Description: {rule['description']}\n"
            text += f"Examples: {', '.join(rule['examples'])}\n"
            text += f"Action: {rule['action']}"

            doc = Document(
                id=f"triage_esi_{rule['level']}",
                text=text,
                metadata={
                    "level": rule["level"],
                    "name": rule["name"],
                    "type": "triage_rule"
                },
                level="carepath"
            )
            self.documents.append(doc)

        return len(triage_rules)

    def load_department_routing(self) -> int:
        """Load department routing rules."""

        departments = [
            {
                "name": "Emergency Department",
                "name_zh": "急诊科",
                "conditions": [
                    "Cardiac arrest", "Stroke", "Major trauma",
                    "Severe bleeding", "Anaphylaxis", "Respiratory failure"
                ],
                "symptoms": [
                    "Chest pain with risk factors", "Sudden weakness",
                    "Difficulty breathing", "Severe pain", "Loss of consciousness"
                ],
                "urgency": ["ESI 1", "ESI 2"],
                "hours": "24/7"
            },
            {
                "name": "Cardiology",
                "name_zh": "心内科",
                "conditions": [
                    "Angina", "Heart failure", "Arrhythmia",
                    "Myocardial infarction (post-acute)", "Hypertension"
                ],
                "symptoms": [
                    "Chest pain", "Palpitations", "Shortness of breath on exertion",
                    "Leg swelling", "Fatigue with cardiac history"
                ],
                "urgency": ["ESI 2", "ESI 3"],
                "hours": "Mon-Fri 8am-5pm, on-call 24/7"
            },
            {
                "name": "Neurology",
                "name_zh": "神经内科",
                "conditions": [
                    "Stroke", "Seizure", "Migraine", "Multiple sclerosis",
                    "Parkinson's disease", "Neuropathy"
                ],
                "symptoms": [
                    "Sudden weakness", "Speech difficulty", "Severe headache",
                    "Numbness", "Vision changes", "Seizure"
                ],
                "urgency": ["ESI 1", "ESI 2", "ESI 3"],
                "hours": "Mon-Fri 8am-5pm, stroke team 24/7"
            },
            {
                "name": "Pulmonology",
                "name_zh": "呼吸内科",
                "conditions": [
                    "Asthma", "COPD", "Pneumonia", "Pulmonary embolism",
                    "Lung cancer", "Sleep apnea"
                ],
                "symptoms": [
                    "Shortness of breath", "Chronic cough", "Wheezing",
                    "Coughing blood", "Chest tightness"
                ],
                "urgency": ["ESI 2", "ESI 3", "ESI 4"],
                "hours": "Mon-Fri 8am-5pm"
            },
            {
                "name": "Gastroenterology",
                "name_zh": "消化内科",
                "conditions": [
                    "GERD", "Peptic ulcer", "Inflammatory bowel disease",
                    "Hepatitis", "Pancreatitis", "GI bleeding"
                ],
                "symptoms": [
                    "Abdominal pain", "Nausea/vomiting", "Diarrhea",
                    "Blood in stool", "Difficulty swallowing", "Jaundice"
                ],
                "urgency": ["ESI 2", "ESI 3", "ESI 4"],
                "hours": "Mon-Fri 8am-5pm"
            },
            {
                "name": "General Practice / Primary Care",
                "name_zh": "全科/内科",
                "conditions": [
                    "Common cold", "Minor infections", "Chronic disease management",
                    "Preventive care", "Minor injuries"
                ],
                "symptoms": [
                    "Mild fever", "Cold symptoms", "Minor pain",
                    "Routine follow-up", "Medication refills"
                ],
                "urgency": ["ESI 4", "ESI 5"],
                "hours": "Mon-Fri 8am-5pm"
            }
        ]

        for dept in departments:
            text = f"Department: {dept['name']} ({dept['name_zh']})\n"
            text += f"Conditions treated: {', '.join(dept['conditions'])}\n"
            text += f"Common symptoms: {', '.join(dept['symptoms'])}\n"
            text += f"Urgency levels: {', '.join(dept['urgency'])}\n"
            text += f"Hours: {dept['hours']}"

            doc = Document(
                id=f"dept_{dept['name'].lower().replace(' ', '_')}",
                text=text,
                metadata={
                    "name": dept["name"],
                    "name_zh": dept["name_zh"],
                    "type": "department"
                },
                level="carepath"
            )
            self.documents.append(doc)

        return len(departments)

    def load_red_flags(self) -> int:
        """Load red flag detection rules."""

        red_flags = [
            {
                "category": "Cardiac",
                "symptoms": ["Crushing chest pain", "Pain radiating to arm/jaw", "Diaphoresis with chest pain"],
                "action": "Immediate cardiac evaluation, call 911/120",
                "urgency": "ESI 1-2"
            },
            {
                "category": "Stroke",
                "symptoms": ["Sudden facial droop", "Arm weakness", "Speech difficulty", "Sudden severe headache"],
                "action": "FAST assessment, immediate stroke team activation",
                "urgency": "ESI 1"
            },
            {
                "category": "Respiratory",
                "symptoms": ["Severe difficulty breathing", "Unable to speak in full sentences", "Cyanosis"],
                "action": "Immediate airway assessment",
                "urgency": "ESI 1-2"
            },
            {
                "category": "Bleeding",
                "symptoms": ["Uncontrolled bleeding", "Vomiting blood", "Blood in stool (large amount)"],
                "action": "Control bleeding, IV access, type and screen",
                "urgency": "ESI 1-2"
            },
            {
                "category": "Neurological",
                "symptoms": ["Sudden loss of consciousness", "Seizure", "Sudden vision loss"],
                "action": "Protect airway, neurological assessment",
                "urgency": "ESI 1-2"
            }
        ]

        for rf in red_flags:
            text = f"Red Flag Category: {rf['category']}\n"
            text += f"Warning symptoms: {', '.join(rf['symptoms'])}\n"
            text += f"Required action: {rf['action']}\n"
            text += f"Urgency: {rf['urgency']}"

            doc = Document(
                id=f"redflag_{rf['category'].lower()}",
                text=text,
                metadata={
                    "category": rf["category"],
                    "urgency": rf["urgency"],
                    "type": "red_flag"
                },
                level="carepath"
            )
            self.documents.append(doc)

        return len(red_flags)

    def build_index(self, output_name: str = "carepath_store"):
        """Build FAISS index from documents."""
        import faiss
        import numpy as np

        if not self.documents:
            logger.error("No documents to index")
            return

        texts = [doc.text for doc in self.documents]
        embeddings = batch_embed(texts)

        embeddings_np = np.array(embeddings).astype('float32')
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        faiss.normalize_L2(embeddings_np)
        index.add(embeddings_np)

        index_path = INDEX_DIR / f"{output_name}.index"
        faiss.write_index(index, str(index_path))

        ids_path = INDEX_DIR / f"{output_name}_docs.json"
        docs_data = [
            {"id": doc.id, "text": doc.text, "metadata": doc.metadata}
            for doc in self.documents
        ]
        with open(ids_path, 'w', encoding='utf-8') as f:
            json.dump(docs_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Built carepath index with {len(self.documents)} documents")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build vector stores for triage agent")
    parser.add_argument("--store", choices=["symptom", "condition", "carepath", "all"],
                        default="all", help="Which store to build")
    parser.add_argument("--guidelines-dir", type=str, default="./data/guidelines",
                        help="Directory containing guideline JSON files")
    args = parser.parse_args()

    if args.store in ["symptom", "all"]:
        logger.info("Building Symptom Vector Store...")
        builder = SymptomStoreBuilder()
        builder.load_from_snomed(limit=5000)
        builder.build_index()

    if args.store in ["condition", "all"]:
        logger.info("Building Condition Vector Store...")
        builder = ConditionStoreBuilder()
        builder.load_from_snomed_diseases(limit=3000)
        builder.load_from_guidelines(args.guidelines_dir)
        builder.build_index()

    if args.store in ["carepath", "all"]:
        logger.info("Building Care-Path Vector Store...")
        builder = CarePathStoreBuilder()
        builder.load_triage_rules()
        builder.load_department_routing()
        builder.load_red_flags()
        builder.build_index()

    logger.info("Done!")


if __name__ == "__main__":
    main()
