"""
Load Clinical Decision Rules into Neo4j and FAISS
==================================================

This script loads clinical decision rules from JSON files and:
1. Creates ClinicalRule, Criterion, and Action nodes in Neo4j
2. Creates relationships linking to SNOMED CT concepts
3. Loads text chunks into PostgreSQL + FAISS for semantic search

Usage:
    python data_pipeline/load_clinical_rules.py [--neo4j] [--faiss] [--all]

Options:
    --neo4j     Load rules into Neo4j only
    --faiss     Load text chunks into FAISS only
    --all       Load both (default)
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Paths
RULES_DIR = Path(__file__).parent / "clinical_rules"


class ClinicalRulesLoader:
    """Load clinical decision rules into Neo4j."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def create_indexes(self):
        """Create indexes for clinical rule nodes."""
        driver = self._get_driver()

        index_queries = [
            "CREATE INDEX clinical_rule_id IF NOT EXISTS FOR (r:ClinicalRule) ON (r.rule_id)",
            "CREATE INDEX criterion_id IF NOT EXISTS FOR (c:Criterion) ON (c.criterion_id)",
            "CREATE INDEX guideline_id IF NOT EXISTS FOR (g:Guideline) ON (g.source)",
            "CREATE INDEX action_type IF NOT EXISTS FOR (a:Action) ON (a.type)",
        ]

        with driver.session() as session:
            for query in index_queries:
                try:
                    session.run(query)
                    logger.info(f"Index created: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation skipped: {e}")

    def load_guideline(self, rule_data: Dict) -> None:
        """Load a guideline and its decision rules into Neo4j."""
        driver = self._get_driver()

        condition = rule_data.get("condition", "Unknown")
        condition_sctid = rule_data.get("condition_sctid", "")
        source = rule_data.get("guideline_source", "")

        logger.info(f"Loading guideline: {source} for {condition}")

        with driver.session() as session:
            # Create Guideline node
            session.run("""
                MERGE (g:Guideline {source: $source})
                SET g.condition = $condition,
                    g.condition_sctid = $condition_sctid,
                    g.url = $url,
                    g.version = $version,
                    g.last_updated = $last_updated,
                    g.description = $description
            """,
                source=source,
                condition=condition,
                condition_sctid=condition_sctid,
                url=rule_data.get("guideline_url", ""),
                version=rule_data.get("version", "1.0"),
                last_updated=rule_data.get("last_updated", ""),
                description=rule_data.get("description", "")
            )

            # Link guideline to SNOMED concept if exists
            if condition_sctid:
                session.run("""
                    MATCH (g:Guideline {source: $source})
                    MATCH (c:ObjectConcept {sctid: $sctid})
                    MERGE (g)-[:APPLIES_TO]->(c)
                """, source=source, sctid=condition_sctid)

            # Load decision rules
            for rule in rule_data.get("decision_rules", []):
                self._load_decision_rule(session, rule, source)

            # Load clarifying questions
            for question in rule_data.get("clarifying_questions", []):
                self._load_question(session, question, source)

    def _load_decision_rule(self, session, rule: Dict, guideline_source: str) -> None:
        """Load a single decision rule."""
        rule_id = rule.get("rule_id", "")
        rule_name = rule.get("rule_name", "")
        risk_level = rule.get("risk_level", "MEDIUM")

        logger.debug(f"  Loading rule: {rule_id} - {rule_name}")

        # Create ClinicalRule node
        session.run("""
            MERGE (r:ClinicalRule {rule_id: $rule_id})
            SET r.name = $name,
                r.risk_level = $risk_level,
                r.description = $description,
                r.evidence_text = $evidence_text,
                r.guideline_source = $guideline_source
        """,
            rule_id=rule_id,
            name=rule_name,
            risk_level=risk_level,
            description=rule.get("description", ""),
            evidence_text=rule.get("evidence_text", ""),
            guideline_source=guideline_source
        )

        # Link to guideline
        session.run("""
            MATCH (r:ClinicalRule {rule_id: $rule_id})
            MATCH (g:Guideline {source: $source})
            MERGE (r)-[:DEFINED_IN]->(g)
        """, rule_id=rule_id, source=guideline_source)

        # Create criteria nodes and link
        for criterion in rule.get("criteria", []):
            self._load_criterion(session, criterion, rule_id)

        # Create action node and link
        action = rule.get("action", {})
        if action:
            self._load_action(session, action, rule_id)

    def _load_criterion(self, session, criterion: Dict, rule_id: str) -> None:
        """Load a criterion and link to rule and SNOMED."""
        criterion_id = criterion.get("criterion_id", "")

        # Create Criterion node
        session.run("""
            MERGE (c:Criterion {criterion_id: $criterion_id})
            SET c.type = $type,
                c.name = $name,
                c.operator = $operator,
                c.threshold = $threshold,
                c.unit = $unit,
                c.keywords = $keywords,
                c.snomed_code = $snomed_code
        """,
            criterion_id=criterion_id,
            type=criterion.get("type", ""),
            name=criterion.get("name", ""),
            operator=criterion.get("operator", ""),
            threshold=str(criterion.get("threshold", "")),
            unit=criterion.get("unit", ""),
            keywords=criterion.get("keywords", []),
            snomed_code=criterion.get("snomed_code", "")
        )

        # Link to rule
        session.run("""
            MATCH (r:ClinicalRule {rule_id: $rule_id})
            MATCH (c:Criterion {criterion_id: $criterion_id})
            MERGE (c)-[:TRIGGERS]->(r)
        """, rule_id=rule_id, criterion_id=criterion_id)

        # Link to SNOMED concept if code exists
        snomed_code = criterion.get("snomed_code", "")
        if snomed_code:
            result = session.run("""
                MATCH (crit:Criterion {criterion_id: $criterion_id})
                MATCH (concept:ObjectConcept {sctid: $sctid})
                MERGE (crit)-[:MAPS_TO]->(concept)
                RETURN concept.FSN as fsn
            """, criterion_id=criterion_id, sctid=snomed_code)
            record = result.single()
            if record:
                logger.debug(f"    Linked criterion to SNOMED: {record['fsn']}")

    def _load_action(self, session, action: Dict, rule_id: str) -> None:
        """Load an action and link to rule."""
        action_type = action.get("type", "workup")
        urgency = action.get("urgency", "ROUTINE")

        # Create Action node with unique ID based on rule
        action_id = f"{rule_id}_ACTION"

        session.run("""
            MERGE (a:Action {action_id: $action_id})
            SET a.type = $type,
                a.urgency = $urgency,
                a.rationale = $rationale,
                a.procedure = $procedure,
                a.tests = $tests,
                a.target_time = $target_time
        """,
            action_id=action_id,
            type=action_type,
            urgency=urgency,
            rationale=action.get("rationale", ""),
            procedure=action.get("procedure", ""),
            tests=action.get("tests", []),
            target_time=action.get("target_time", "")
        )

        # Link to rule
        session.run("""
            MATCH (r:ClinicalRule {rule_id: $rule_id})
            MATCH (a:Action {action_id: $action_id})
            MERGE (r)-[:RECOMMENDS]->(a)
        """, rule_id=rule_id, action_id=action_id)

    def _load_question(self, session, question: Dict, guideline_source: str) -> None:
        """Load a clarifying question."""
        question_id = question.get("question_id", "")

        session.run("""
            MERGE (q:ClarifyingQuestion {question_id: $question_id})
            SET q.question = $question,
                q.question_zh = $question_zh,
                q.target_criterion = $target_criterion,
                q.response_type = $response_type,
                q.priority = $priority,
                q.guideline_source = $guideline_source
        """,
            question_id=question_id,
            question=question.get("question", ""),
            question_zh=question.get("question_zh", ""),
            target_criterion=question.get("target_criterion", ""),
            response_type=question.get("response_type", "text"),
            priority=question.get("priority", 2),
            guideline_source=guideline_source
        )

        # Link to criterion
        target = question.get("target_criterion", "")
        if target:
            session.run("""
                MATCH (q:ClarifyingQuestion {question_id: $question_id})
                MATCH (c:Criterion {criterion_id: $target})
                MERGE (q)-[:ASKS_ABOUT]->(c)
            """, question_id=question_id, target=target)

    def load_all_rules(self) -> Dict[str, int]:
        """Load all clinical rules from JSON files."""
        stats = {
            "guidelines": 0,
            "rules": 0,
            "criteria": 0,
            "actions": 0,
            "questions": 0
        }

        # Create indexes first
        self.create_indexes()

        # Load all JSON files in the rules directory
        for json_file in RULES_DIR.glob("*.json"):
            logger.info(f"Loading: {json_file.name}")

            with open(json_file, "r", encoding="utf-8") as f:
                rule_data = json.load(f)

            self.load_guideline(rule_data)

            stats["guidelines"] += 1
            stats["rules"] += len(rule_data.get("decision_rules", []))
            stats["questions"] += len(rule_data.get("clarifying_questions", []))

            for rule in rule_data.get("decision_rules", []):
                stats["criteria"] += len(rule.get("criteria", []))
                if rule.get("action"):
                    stats["actions"] += 1

        self.close()
        return stats


class TextChunksLoader:
    """Load text chunks into PostgreSQL and FAISS."""

    def __init__(self):
        self.chunks_loaded = 0

    def load_chunks_from_rules(self) -> int:
        """Extract and load text chunks from clinical rules JSON files."""
        try:
            from data_pipeline.common_db import pg_conn
            from data_pipeline.embedder import embed
        except ModuleNotFoundError:
            from common_db import pg_conn
            from embedder import embed
        import numpy as np

        all_chunks = []

        # Extract chunks from all JSON files
        for json_file in RULES_DIR.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                rule_data = json.load(f)

            condition = rule_data.get("condition", "Unknown")
            source = rule_data.get("guideline_source", "")

            for chunk in rule_data.get("text_chunks", []):
                all_chunks.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "title": chunk.get("title", ""),
                    "chunk_type": chunk.get("chunk_type", ""),
                    "content": chunk.get("content", ""),
                    "source": chunk.get("source", source),
                    "condition": condition,
                    "tags": chunk.get("tags", [])
                })

        if not all_chunks:
            logger.warning("No text chunks found")
            return 0

        logger.info(f"Found {len(all_chunks)} text chunks to load")

        # Generate embeddings
        texts = [c["content"] for c in all_chunks]
        logger.info("Generating embeddings...")
        embeddings = embed(texts)

        # Insert into PostgreSQL
        with pg_conn() as conn:
            cur = conn.cursor()

            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clinical_guideline_chunks (
                    id SERIAL PRIMARY KEY,
                    chunk_id TEXT UNIQUE,
                    title TEXT,
                    chunk_type TEXT,
                    content TEXT,
                    source TEXT,
                    condition TEXT,
                    tags TEXT[],
                    embedding BYTEA,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Insert chunks
            for i, chunk in enumerate(all_chunks):
                try:
                    cur.execute("""
                        INSERT INTO clinical_guideline_chunks
                        (chunk_id, title, chunk_type, content, source, condition, tags, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding
                    """, (
                        chunk["chunk_id"],
                        chunk["title"],
                        chunk["chunk_type"],
                        chunk["content"],
                        chunk["source"],
                        chunk["condition"],
                        chunk["tags"],
                        embeddings[i].tobytes()
                    ))
                except Exception as e:
                    logger.error(f"Error inserting chunk {chunk['chunk_id']}: {e}")

            conn.commit()

        logger.info(f"Loaded {len(all_chunks)} chunks into PostgreSQL")

        # Build FAISS index
        self._build_faiss_index(all_chunks, embeddings)

        return len(all_chunks)

    def _build_faiss_index(self, chunks: List[Dict], embeddings) -> None:
        """Build or update FAISS index with new chunks."""
        try:
            import faiss
            import numpy as np

            index_dir = Path("index")
            index_dir.mkdir(exist_ok=True)

            clinical_index_path = index_dir / "faiss_clinical_rules.index"
            clinical_id_map_path = index_dir / "clinical_rules_id_map.npy"

            # Create new index
            d = embeddings.shape[1]  # Dimension
            index = faiss.IndexFlatIP(d)  # Inner product (for normalized vectors)

            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            index.add(embeddings)

            # Save index
            faiss.write_index(index, str(clinical_index_path))

            # Save ID map
            id_map = np.array([c["chunk_id"] for c in chunks])
            np.save(str(clinical_id_map_path), id_map)

            logger.info(f"Built FAISS index with {len(chunks)} vectors at {clinical_index_path}")

        except ImportError:
            logger.warning("FAISS not installed, skipping index build")
        except Exception as e:
            logger.error(f"Error building FAISS index: {e}")


def get_stats() -> Dict[str, int]:
    """Get statistics about loaded clinical rules."""
    try:
        from data_pipeline.neo4j_db import neo4j_conn
    except ModuleNotFoundError:
        # Running as script directly
        from neo4j_db import neo4j_conn

    stats = {}
    queries = {
        "guidelines": "MATCH (g:Guideline) RETURN count(g) as count",
        "clinical_rules": "MATCH (r:ClinicalRule) RETURN count(r) as count",
        "criteria": "MATCH (c:Criterion) RETURN count(c) as count",
        "actions": "MATCH (a:Action) RETURN count(a) as count",
        "questions": "MATCH (q:ClarifyingQuestion) RETURN count(q) as count",
        "snomed_links": "MATCH ()-[r:MAPS_TO]->(:ObjectConcept) RETURN count(r) as count",
    }

    try:
        with neo4j_conn() as session:
            for key, query in queries.items():
                result = session.run(query)
                record = result.single()
                stats[key] = record["count"] if record else 0
    except Exception as e:
        logger.error(f"Error getting stats: {e}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load clinical decision rules")
    parser.add_argument("--neo4j", action="store_true", help="Load into Neo4j only")
    parser.add_argument("--faiss", action="store_true", help="Load into FAISS only")
    parser.add_argument("--all", action="store_true", help="Load both (default)")
    parser.add_argument("--stats", action="store_true", help="Show current stats only")

    args = parser.parse_args()

    # Default to --all if no specific option
    if not args.neo4j and not args.faiss and not args.stats:
        args.all = True

    if args.stats:
        stats = get_stats()
        print("\n" + "=" * 50)
        print("Clinical Rules Database Statistics")
        print("=" * 50)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return

    print("\n" + "=" * 50)
    print("Loading Clinical Decision Rules")
    print("=" * 50)

    if args.neo4j or args.all:
        print("\n--- Loading into Neo4j ---")
        loader = ClinicalRulesLoader()
        stats = loader.load_all_rules()
        print(f"Loaded: {stats}")

    if args.faiss or args.all:
        print("\n--- Loading text chunks into FAISS ---")
        chunks_loader = TextChunksLoader()
        count = chunks_loader.load_chunks_from_rules()
        print(f"Loaded {count} text chunks")

    # Show final stats
    print("\n--- Final Statistics ---")
    stats = get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
