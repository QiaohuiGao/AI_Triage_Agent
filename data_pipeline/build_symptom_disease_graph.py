"""
Build Symptom-Disease Relationship Graph in Neo4j
=================================================

This script extends the existing SNOMED CT graph with:
1. MAY_INDICATE relationships (symptom -> disease)
2. HAS_RED_FLAG labels for critical symptoms
3. TRIAGE_PRIORITY properties
4. ROUTES_TO relationships (disease -> department)

This enables graph-based clinical reasoning alongside the rule-based approach.

Usage:
    python build_symptom_disease_graph.py

Note: This script is idempotent - safe to run multiple times.
"""

import os
from typing import List, Dict, Any
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Symptom-Disease Relationships Data
# ---------------------------------------------------------------------------

# Format: symptom_sctid -> [(disease_sctid, probability, is_red_flag), ...]
SYMPTOM_DISEASE_RELATIONSHIPS = [
    # === CHEST PAIN related ===
    {
        "symptom_sctid": "29857009",  # Chest pain
        "symptom_name": "Chest pain",
        "diseases": [
            {"sctid": "22298006", "name": "Myocardial infarction", "probability": 0.3, "is_red_flag": True},
            {"sctid": "194828000", "name": "Angina pectoris", "probability": 0.25, "is_red_flag": False},
            {"sctid": "233604007", "name": "Pneumonia", "probability": 0.15, "is_red_flag": False},
            {"sctid": "371631005", "name": "Panic disorder", "probability": 0.15, "is_red_flag": False},
            {"sctid": "235595009", "name": "Gastroesophageal reflux", "probability": 0.1, "is_red_flag": False},
        ]
    },
    {
        "symptom_sctid": "10000006",  # Radiating chest pain
        "symptom_name": "Radiating chest pain",
        "diseases": [
            {"sctid": "22298006", "name": "Myocardial infarction", "probability": 0.6, "is_red_flag": True},
            {"sctid": "194828000", "name": "Angina pectoris", "probability": 0.3, "is_red_flag": True},
        ]
    },

    # === HEADACHE related ===
    {
        "symptom_sctid": "25064002",  # Headache
        "symptom_name": "Headache",
        "diseases": [
            {"sctid": "37796009", "name": "Migraine", "probability": 0.35, "is_red_flag": False},
            {"sctid": "230690007", "name": "Stroke", "probability": 0.05, "is_red_flag": True},  # If sudden severe
            {"sctid": "4969004", "name": "Sinus headache", "probability": 0.25, "is_red_flag": False},
            {"sctid": "55865003", "name": "Cluster headache", "probability": 0.1, "is_red_flag": False},
            {"sctid": "398979000", "name": "Tension headache", "probability": 0.2, "is_red_flag": False},
        ]
    },

    # === BREATHING related ===
    {
        "symptom_sctid": "267036007",  # Dyspnea (shortness of breath)
        "symptom_name": "Dyspnea",
        "diseases": [
            {"sctid": "22298006", "name": "Myocardial infarction", "probability": 0.2, "is_red_flag": True},
            {"sctid": "195967001", "name": "Asthma", "probability": 0.25, "is_red_flag": False},
            {"sctid": "233604007", "name": "Pneumonia", "probability": 0.2, "is_red_flag": True},
            {"sctid": "371631005", "name": "Panic disorder", "probability": 0.15, "is_red_flag": False},
            {"sctid": "84114007", "name": "Heart failure", "probability": 0.1, "is_red_flag": True},
        ]
    },

    # === COUGH related ===
    {
        "symptom_sctid": "49727002",  # Cough
        "symptom_name": "Cough",
        "diseases": [
            {"sctid": "54150009", "name": "Upper respiratory infection", "probability": 0.4, "is_red_flag": False},
            {"sctid": "233604007", "name": "Pneumonia", "probability": 0.2, "is_red_flag": False},
            {"sctid": "195967001", "name": "Asthma", "probability": 0.15, "is_red_flag": False},
            {"sctid": "235595009", "name": "GERD", "probability": 0.1, "is_red_flag": False},
            {"sctid": "13645005", "name": "COPD", "probability": 0.1, "is_red_flag": False},
        ]
    },

    # === FEVER related ===
    {
        "symptom_sctid": "386661006",  # Fever
        "symptom_name": "Fever",
        "diseases": [
            {"sctid": "54150009", "name": "Upper respiratory infection", "probability": 0.35, "is_red_flag": False},
            {"sctid": "233604007", "name": "Pneumonia", "probability": 0.2, "is_red_flag": False},
            {"sctid": "25374005", "name": "Gastroenteritis", "probability": 0.15, "is_red_flag": False},
            {"sctid": "68566005", "name": "Urinary tract infection", "probability": 0.15, "is_red_flag": False},
            {"sctid": "409822003", "name": "Influenza", "probability": 0.1, "is_red_flag": False},
        ]
    },

    # === ABDOMINAL PAIN related ===
    {
        "symptom_sctid": "21522001",  # Abdominal pain
        "symptom_name": "Abdominal pain",
        "diseases": [
            {"sctid": "25374005", "name": "Gastroenteritis", "probability": 0.25, "is_red_flag": False},
            {"sctid": "74400008", "name": "Appendicitis", "probability": 0.15, "is_red_flag": True},
            {"sctid": "235595009", "name": "GERD", "probability": 0.15, "is_red_flag": False},
            {"sctid": "235796008", "name": "Peptic ulcer", "probability": 0.1, "is_red_flag": False},
            {"sctid": "48340000", "name": "Cholecystitis", "probability": 0.1, "is_red_flag": True},
        ]
    },

    # === NAUSEA/VOMITING related ===
    {
        "symptom_sctid": "422587007",  # Nausea
        "symptom_name": "Nausea",
        "diseases": [
            {"sctid": "25374005", "name": "Gastroenteritis", "probability": 0.3, "is_red_flag": False},
            {"sctid": "37796009", "name": "Migraine", "probability": 0.2, "is_red_flag": False},
            {"sctid": "22298006", "name": "Myocardial infarction", "probability": 0.1, "is_red_flag": True},
            {"sctid": "74400008", "name": "Appendicitis", "probability": 0.1, "is_red_flag": False},
        ]
    },

    # === SWEATING related (important cardiac indicator) ===
    {
        "symptom_sctid": "415690000",  # Sweating / Diaphoresis
        "symptom_name": "Diaphoresis",
        "diseases": [
            {"sctid": "22298006", "name": "Myocardial infarction", "probability": 0.4, "is_red_flag": True},
            {"sctid": "371631005", "name": "Panic disorder", "probability": 0.2, "is_red_flag": False},
            {"sctid": "386661006", "name": "Fever condition", "probability": 0.2, "is_red_flag": False},
        ]
    },

    # === DIZZINESS related ===
    {
        "symptom_sctid": "404640003",  # Dizziness
        "symptom_name": "Dizziness",
        "diseases": [
            {"sctid": "230690007", "name": "Stroke", "probability": 0.1, "is_red_flag": True},
            {"sctid": "271594007", "name": "Syncope", "probability": 0.15, "is_red_flag": True},
            {"sctid": "422587007", "name": "Vestibular disorder", "probability": 0.25, "is_red_flag": False},
            {"sctid": "84757009", "name": "Hypoglycemia", "probability": 0.15, "is_red_flag": False},
            {"sctid": "45007003", "name": "Hypotension", "probability": 0.1, "is_red_flag": False},
        ]
    },
]


# Disease to Department routing
DISEASE_DEPARTMENT_ROUTING = {
    # Cardiac
    "22298006": {"department": "Emergency", "specialty": "Cardiology", "triage": 1},  # MI
    "194828000": {"department": "Cardiology", "specialty": "Cardiology", "triage": 2},  # Angina
    "84114007": {"department": "Emergency", "specialty": "Cardiology", "triage": 2},  # Heart failure

    # Neurological
    "230690007": {"department": "Emergency", "specialty": "Neurology", "triage": 1},  # Stroke
    "37796009": {"department": "Neurology", "specialty": "Neurology", "triage": 3},  # Migraine

    # Respiratory
    "233604007": {"department": "Emergency", "specialty": "Pulmonology", "triage": 2},  # Pneumonia
    "195967001": {"department": "Pulmonology", "specialty": "Pulmonology", "triage": 3},  # Asthma
    "54150009": {"department": "General Practice", "specialty": "Internal Medicine", "triage": 4},  # URI

    # Gastrointestinal
    "74400008": {"department": "Emergency", "specialty": "Surgery", "triage": 2},  # Appendicitis
    "25374005": {"department": "Gastroenterology", "specialty": "Gastroenterology", "triage": 3},  # Gastroenteritis
    "48340000": {"department": "Emergency", "specialty": "Surgery", "triage": 2},  # Cholecystitis

    # Psychiatric
    "371631005": {"department": "Psychiatry", "specialty": "Psychiatry", "triage": 3},  # Panic disorder

    # General
    "409822003": {"department": "General Practice", "specialty": "Internal Medicine", "triage": 4},  # Flu
}


# ---------------------------------------------------------------------------
# Neo4j Graph Builder
# ---------------------------------------------------------------------------

class SymptomDiseaseGraphBuilder:
    """Build symptom-disease relationships in Neo4j."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")

    def _get_driver(self):
        from neo4j import GraphDatabase
        return GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    def create_indexes(self):
        """Create necessary indexes for efficient querying."""
        driver = self._get_driver()

        index_queries = [
            # Index for faster symptom-disease lookup
            "CREATE INDEX symptom_disease_idx IF NOT EXISTS FOR ()-[r:MAY_INDICATE]->() ON (r.probability)",
            # Index for department routing
            "CREATE INDEX department_idx IF NOT EXISTS FOR ()-[r:ROUTES_TO]->() ON (r.triage_level)",
        ]

        with driver.session() as session:
            for query in index_queries:
                try:
                    session.run(query)
                    logger.info(f"Created index: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation skipped: {e}")

        driver.close()

    def create_department_nodes(self):
        """Create department nodes for routing."""
        driver = self._get_driver()

        departments = [
            ("Emergency", "急诊科"),
            ("Cardiology", "心内科"),
            ("Neurology", "神经内科"),
            ("Pulmonology", "呼吸内科"),
            ("Gastroenterology", "消化内科"),
            ("Surgery", "外科"),
            ("Psychiatry", "精神科"),
            ("General Practice", "全科"),
            ("Internal Medicine", "内科"),
        ]

        query = """
        MERGE (d:Department {name: $name})
        SET d.name_zh = $name_zh
        RETURN d
        """

        with driver.session() as session:
            for name, name_zh in departments:
                session.run(query, name=name, name_zh=name_zh)
                logger.info(f"Created department: {name}")

        driver.close()

    def create_symptom_disease_relationships(self):
        """Create MAY_INDICATE relationships from symptoms to diseases."""
        driver = self._get_driver()

        # Query to create relationship
        create_rel_query = """
        MATCH (symptom:ObjectConcept {sctid: $symptom_sctid})
        MATCH (disease:ObjectConcept {sctid: $disease_sctid})
        MERGE (symptom)-[r:MAY_INDICATE]->(disease)
        SET r.probability = $probability,
            r.is_red_flag = $is_red_flag,
            r.source = 'clinical_rules'
        RETURN symptom.FSN as symptom_name, disease.FSN as disease_name
        """

        with driver.session() as session:
            for symptom_data in SYMPTOM_DISEASE_RELATIONSHIPS:
                symptom_sctid = symptom_data["symptom_sctid"]

                for disease in symptom_data["diseases"]:
                    try:
                        result = session.run(
                            create_rel_query,
                            symptom_sctid=symptom_sctid,
                            disease_sctid=disease["sctid"],
                            probability=disease["probability"],
                            is_red_flag=disease["is_red_flag"]
                        )
                        record = result.single()
                        if record:
                            logger.info(
                                f"Created: {record['symptom_name']} "
                                f"--[MAY_INDICATE {disease['probability']}]--> "
                                f"{record['disease_name']}"
                            )
                        else:
                            logger.warning(
                                f"Nodes not found: {symptom_sctid} -> {disease['sctid']}"
                            )
                    except Exception as e:
                        logger.error(f"Error creating relationship: {e}")

        driver.close()

    def create_department_routing(self):
        """Create ROUTES_TO relationships from diseases to departments."""
        driver = self._get_driver()

        query = """
        MATCH (disease:ObjectConcept {sctid: $disease_sctid})
        MATCH (dept:Department {name: $department})
        MERGE (disease)-[r:ROUTES_TO]->(dept)
        SET r.triage_level = $triage_level,
            r.specialty = $specialty
        RETURN disease.FSN as disease_name, dept.name as department
        """

        with driver.session() as session:
            for disease_sctid, routing in DISEASE_DEPARTMENT_ROUTING.items():
                try:
                    result = session.run(
                        query,
                        disease_sctid=disease_sctid,
                        department=routing["department"],
                        triage_level=routing["triage"],
                        specialty=routing["specialty"]
                    )
                    record = result.single()
                    if record:
                        logger.info(
                            f"Routed: {record['disease_name']} "
                            f"--[ROUTES_TO]--> {record['department']}"
                        )
                except Exception as e:
                    logger.error(f"Error creating routing: {e}")

        driver.close()

    def add_red_flag_labels(self):
        """Add :RedFlag label to critical symptoms."""
        driver = self._get_driver()

        red_flag_symptoms = [
            "29857009",   # Chest pain
            "10000006",   # Radiating chest pain
            "267036007",  # Dyspnea
            "419045004",  # Loss of consciousness
            "271594007",  # Syncope
            "131148009",  # Bleeding
            "398979000",  # Facial weakness
            "29164008",   # Speech disturbance
        ]

        query = """
        MATCH (c:ObjectConcept {sctid: $sctid})
        SET c:RedFlag
        SET c.red_flag_action = $action
        RETURN c.FSN as name
        """

        actions = {
            "29857009": "Assess for cardiac emergency",
            "10000006": "Assess for MI - Call 120",
            "267036007": "Assess airway - possible emergency",
            "419045004": "Call 120 immediately",
            "271594007": "Assess for cardiac/neurological cause",
            "131148009": "Control bleeding, assess shock",
            "398979000": "FAST stroke assessment",
            "29164008": "FAST stroke assessment",
        }

        with driver.session() as session:
            for sctid in red_flag_symptoms:
                action = actions.get(sctid, "Urgent assessment needed")
                result = session.run(query, sctid=sctid, action=action)
                record = result.single()
                if record:
                    logger.info(f"Added RedFlag label to: {record['name']}")

        driver.close()

    def build_all(self):
        """Run all build steps."""
        logger.info("Starting symptom-disease graph build...")

        logger.info("Step 1: Creating indexes...")
        self.create_indexes()

        logger.info("Step 2: Creating department nodes...")
        self.create_department_nodes()

        logger.info("Step 3: Creating symptom-disease relationships...")
        self.create_symptom_disease_relationships()

        logger.info("Step 4: Creating department routing...")
        self.create_department_routing()

        logger.info("Step 5: Adding red flag labels...")
        self.add_red_flag_labels()

        logger.info("Symptom-disease graph build complete!")

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the symptom-disease graph."""
        driver = self._get_driver()

        queries = {
            "may_indicate_count": "MATCH ()-[r:MAY_INDICATE]->() RETURN count(r) as count",
            "routes_to_count": "MATCH ()-[r:ROUTES_TO]->() RETURN count(r) as count",
            "red_flag_count": "MATCH (c:RedFlag) RETURN count(c) as count",
            "department_count": "MATCH (d:Department) RETURN count(d) as count",
        }

        stats = {}
        with driver.session() as session:
            for key, query in queries.items():
                result = session.run(query)
                record = result.single()
                stats[key] = record["count"] if record else 0

        driver.close()
        return stats


# ---------------------------------------------------------------------------
# Graph-based Reasoning Queries
# ---------------------------------------------------------------------------

class GraphBasedReasoner:
    """Use Neo4j graph for clinical reasoning."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")

    def _get_driver(self):
        from neo4j import GraphDatabase
        return GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    def find_diseases_for_symptoms(
        self,
        symptom_sctids: List[str],
        min_probability: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Find possible diseases based on symptoms using graph traversal.

        Args:
            symptom_sctids: List of SNOMED CT symptom codes
            min_probability: Minimum probability threshold

        Returns:
            List of disease candidates with aggregated probabilities
        """
        driver = self._get_driver()

        query = """
        UNWIND $symptom_sctids AS symptom_id
        MATCH (symptom:ObjectConcept {sctid: symptom_id})-[r:MAY_INDICATE]->(disease:ObjectConcept)
        WHERE r.probability >= $min_probability
        WITH disease,
             collect(symptom.sctid) AS matching_symptoms,
             collect(r.probability) AS probabilities,
             max(r.is_red_flag) AS has_red_flag
        OPTIONAL MATCH (disease)-[route:ROUTES_TO]->(dept:Department)
        RETURN disease.sctid AS sctid,
               disease.FSN AS name,
               matching_symptoms,
               probabilities,
               reduce(total = 0.0, p IN probabilities | total + p) / size(probabilities) AS avg_probability,
               size(matching_symptoms) AS symptom_match_count,
               has_red_flag,
               dept.name AS department,
               route.triage_level AS triage_level
        ORDER BY symptom_match_count DESC, avg_probability DESC
        LIMIT 10
        """

        results = []
        with driver.session() as session:
            result = session.run(
                query,
                symptom_sctids=symptom_sctids,
                min_probability=min_probability
            )
            for record in result:
                results.append({
                    "sctid": record["sctid"],
                    "name": record["name"],
                    "matching_symptoms": record["matching_symptoms"],
                    "avg_probability": record["avg_probability"],
                    "symptom_match_count": record["symptom_match_count"],
                    "has_red_flag": record["has_red_flag"],
                    "department": record["department"],
                    "triage_level": record["triage_level"],
                })

        driver.close()
        return results

    def check_red_flags(self, symptom_sctids: List[str]) -> List[Dict[str, str]]:
        """Check if any symptoms are red flags."""
        driver = self._get_driver()

        query = """
        UNWIND $symptom_sctids AS symptom_id
        MATCH (symptom:ObjectConcept:RedFlag {sctid: symptom_id})
        RETURN symptom.sctid AS sctid,
               symptom.FSN AS name,
               symptom.red_flag_action AS action
        """

        results = []
        with driver.session() as session:
            result = session.run(query, symptom_sctids=symptom_sctids)
            for record in result:
                results.append({
                    "sctid": record["sctid"],
                    "name": record["name"],
                    "action": record["action"],
                })

        driver.close()
        return results

    def get_disease_details(self, disease_sctid: str) -> Optional[Dict[str, Any]]:
        """Get full details for a disease including routing."""
        driver = self._get_driver()

        query = """
        MATCH (disease:ObjectConcept {sctid: $sctid})
        OPTIONAL MATCH (disease)-[route:ROUTES_TO]->(dept:Department)
        OPTIONAL MATCH (symptom:ObjectConcept)-[r:MAY_INDICATE]->(disease)
        RETURN disease.sctid AS sctid,
               disease.FSN AS name,
               dept.name AS department,
               dept.name_zh AS department_zh,
               route.triage_level AS triage_level,
               route.specialty AS specialty,
               collect({sctid: symptom.sctid, name: symptom.FSN, probability: r.probability}) AS related_symptoms
        """

        with driver.session() as session:
            result = session.run(query, sctid=disease_sctid)
            record = result.single()
            if record:
                return {
                    "sctid": record["sctid"],
                    "name": record["name"],
                    "department": record["department"],
                    "department_zh": record["department_zh"],
                    "triage_level": record["triage_level"],
                    "specialty": record["specialty"],
                    "related_symptoms": record["related_symptoms"],
                }

        driver.close()
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        # Build the graph
        builder = SymptomDiseaseGraphBuilder()
        builder.build_all()

        # Show stats
        stats = builder.get_stats()
        print("\n=== Graph Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test reasoning
        reasoner = GraphBasedReasoner()

        print("\n=== Testing Graph-based Reasoning ===")

        # Test: Chest pain + sweating
        symptoms = ["29857009", "415690000"]  # Chest pain, sweating
        print(f"\nSymptoms: {symptoms}")

        # Check red flags
        red_flags = reasoner.check_red_flags(symptoms)
        print(f"Red flags: {red_flags}")

        # Find diseases
        diseases = reasoner.find_diseases_for_symptoms(symptoms)
        print(f"Possible diseases:")
        for d in diseases[:5]:
            print(f"  - {d['name']} (prob: {d['avg_probability']:.2f}, dept: {d['department']})")

    else:
        print("Usage:")
        print("  python build_symptom_disease_graph.py build  # Build the graph")
        print("  python build_symptom_disease_graph.py test   # Test reasoning")
