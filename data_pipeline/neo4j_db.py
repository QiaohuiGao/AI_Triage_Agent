"""
Neo4j SNOMED CT Database Connection Module
==========================================

This module provides connection and query utilities for the SNOMED CT
knowledge graph stored in Neo4j.

Main Functions:
- neo4j_conn(): Context manager for Neo4j driver connections
- snomed_search(): Search for SNOMED CT concepts by term
- snomed_get_concept(): Get concept details by SNOMED code
- snomed_get_children(): Get child concepts (narrower terms)
- snomed_get_parents(): Get parent concepts (broader terms)
- snomed_find_relationships(): Find relationships for a concept

SNOMED CT Graph Schema (as loaded by snomed-database-loader):
- Nodes: ObjectConcept (with sctid, FSN properties)
- Relationships: ISA (parent-child), Defining relationships (role-value)
"""

import os
from contextlib import contextmanager
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j connection configuration
NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "snomed2024"),
    "database": os.getenv("NEO4J_DATABASE", "neo4j"),
}


def _get_driver():
    """Create and return a Neo4j driver instance."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError(
            "neo4j package not installed. Install with: pip install neo4j"
        )

    return GraphDatabase.driver(
        NEO4J_CONFIG["uri"],
        auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
    )


@contextmanager
def neo4j_conn():
    """
    Context manager for Neo4j connections.

    Usage:
        with neo4j_conn() as session:
            result = session.run("MATCH (n) RETURN n LIMIT 1")
            for record in result:
                print(record)
    """
    driver = _get_driver()
    session = driver.session(database=NEO4J_CONFIG["database"])
    try:
        yield session
    finally:
        session.close()
        driver.close()


def snomed_search(term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search SNOMED CT concepts by term (case-insensitive, partial match).

    Args:
        term: Search term (symptom, condition, etc.)
        limit: Maximum number of results

    Returns:
        List of dictionaries with sctid, FSN (Fully Specified Name), and active status

    Example:
        >>> snomed_search("headache")
        [{'sctid': '25064002', 'fsn': 'Headache (finding)', 'active': True}, ...]
    """
    query = """
    MATCH (c:ObjectConcept)-[:HAS_DESCRIPTION]->(d:Description)
    WHERE toLower(d.term) CONTAINS toLower($term)
    AND d.active = '1'
    RETURN DISTINCT c.sctid AS sctid, c.FSN AS fsn, c.active AS active
    ORDER BY
        CASE WHEN toLower(d.term) = toLower($term) THEN 0 ELSE 1 END,
        size(d.term)
    LIMIT $limit
    """

    with neo4j_conn() as session:
        result = session.run(query, term=term, limit=limit)
        return [
            {
                "sctid": record["sctid"],
                "fsn": record["fsn"],
                "active": record["active"] == "1"
            }
            for record in result
        ]


def snomed_search_simple(term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Simple search using FSN field on ObjectConcept nodes.
    Use this if HAS_DESCRIPTION relationships are not available.

    Args:
        term: Search term
        limit: Maximum results

    Returns:
        List of matching concepts
    """
    query = """
    MATCH (c:ObjectConcept)
    WHERE toLower(c.FSN) CONTAINS toLower($term)
    AND c.active = '1'
    RETURN c.sctid AS sctid, c.FSN AS fsn, c.active AS active
    ORDER BY size(c.FSN)
    LIMIT $limit
    """

    with neo4j_conn() as session:
        result = session.run(query, term=term, limit=limit)
        return [
            {
                "sctid": record["sctid"],
                "fsn": record["fsn"],
                "active": record["active"] == "1"
            }
            for record in result
        ]


def snomed_get_concept(sctid: str) -> Optional[Dict[str, Any]]:
    """
    Get SNOMED CT concept details by SCTID (concept ID).

    Args:
        sctid: SNOMED CT concept identifier

    Returns:
        Dictionary with concept details or None if not found
    """
    query = """
    MATCH (c:ObjectConcept {sctid: $sctid})
    RETURN c.sctid AS sctid, c.FSN AS fsn, c.active AS active
    """

    with neo4j_conn() as session:
        result = session.run(query, sctid=sctid)
        record = result.single()
        if record:
            return {
                "sctid": record["sctid"],
                "fsn": record["fsn"],
                "active": record["active"] == "1"
            }
    return None


def snomed_get_parents(sctid: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get parent concepts (broader terms) via ISA relationships.
    In SNOMED CT, ISA means "is a kind of" (child -> parent).

    Args:
        sctid: SNOMED CT concept identifier
        limit: Maximum number of parents to return

    Returns:
        List of parent concepts
    """
    query = """
    MATCH (c:ObjectConcept {sctid: $sctid})-[:ISA]->(parent:ObjectConcept)
    WHERE parent.active = '1'
    RETURN parent.sctid AS sctid, parent.FSN AS fsn
    LIMIT $limit
    """

    with neo4j_conn() as session:
        result = session.run(query, sctid=sctid, limit=limit)
        return [
            {"sctid": record["sctid"], "fsn": record["fsn"]}
            for record in result
        ]


def snomed_get_children(sctid: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get child concepts (narrower terms) via ISA relationships.

    Args:
        sctid: SNOMED CT concept identifier
        limit: Maximum number of children to return

    Returns:
        List of child concepts
    """
    query = """
    MATCH (child:ObjectConcept)-[:ISA]->(c:ObjectConcept {sctid: $sctid})
    WHERE child.active = '1'
    RETURN child.sctid AS sctid, child.FSN AS fsn
    LIMIT $limit
    """

    with neo4j_conn() as session:
        result = session.run(query, sctid=sctid, limit=limit)
        return [
            {"sctid": record["sctid"], "fsn": record["fsn"]}
            for record in result
        ]


def snomed_get_ancestors(sctid: str, max_depth: int = 5) -> List[Dict[str, Any]]:
    """
    Get all ancestor concepts up to max_depth levels.
    Useful for finding the hierarchy path to root concepts.

    Args:
        sctid: SNOMED CT concept identifier
        max_depth: Maximum hierarchy depth to traverse

    Returns:
        List of ancestor concepts with their depth level
    """
    query = """
    MATCH path = (c:ObjectConcept {sctid: $sctid})-[:ISA*1..%d]->(ancestor:ObjectConcept)
    WHERE ancestor.active = '1'
    RETURN DISTINCT ancestor.sctid AS sctid, ancestor.FSN AS fsn,
           length(path) AS depth
    ORDER BY depth
    """ % max_depth

    with neo4j_conn() as session:
        result = session.run(query, sctid=sctid)
        return [
            {
                "sctid": record["sctid"],
                "fsn": record["fsn"],
                "depth": record["depth"]
            }
            for record in result
        ]


def snomed_find_related(sctid: str) -> List[Dict[str, Any]]:
    """
    Find all defining relationships for a concept.
    These include finding site, associated morphology, etc.

    Args:
        sctid: SNOMED CT concept identifier

    Returns:
        List of relationships with type and target concept
    """
    query = """
    MATCH (c:ObjectConcept {sctid: $sctid})-[r]->(target:ObjectConcept)
    WHERE type(r) <> 'ISA'
    RETURN type(r) AS relationship_type,
           target.sctid AS target_sctid,
           target.FSN AS target_fsn
    """

    with neo4j_conn() as session:
        result = session.run(query, sctid=sctid)
        return [
            {
                "relationship_type": record["relationship_type"],
                "target_sctid": record["target_sctid"],
                "target_fsn": record["target_fsn"]
            }
            for record in result
        ]


def snomed_find_by_category(category_sctid: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Find all concepts that are descendants of a given category.

    Useful category SCTIDs:
    - 404684003: Clinical finding
    - 71388002: Procedure
    - 123037004: Body structure
    - 410607006: Organism
    - 373873005: Pharmaceutical/biologic product

    Args:
        category_sctid: SNOMED CT concept ID for the category
        limit: Maximum results

    Returns:
        List of concepts in that category
    """
    query = """
    MATCH (c:ObjectConcept)-[:ISA*1..10]->(category:ObjectConcept {sctid: $category_sctid})
    WHERE c.active = '1'
    RETURN DISTINCT c.sctid AS sctid, c.FSN AS fsn
    LIMIT $limit
    """

    with neo4j_conn() as session:
        result = session.run(query, category_sctid=category_sctid, limit=limit)
        return [
            {"sctid": record["sctid"], "fsn": record["fsn"]}
            for record in result
        ]


def snomed_is_descendant_of(concept_sctid: str, ancestor_sctid: str) -> bool:
    """
    Check if a concept is a descendant of another concept.
    Useful for categorization (e.g., is this a type of pain?).

    Args:
        concept_sctid: The concept to check
        ancestor_sctid: The potential ancestor

    Returns:
        True if concept is a descendant of ancestor
    """
    query = """
    MATCH path = (c:ObjectConcept {sctid: $concept_sctid})-[:ISA*1..15]->(a:ObjectConcept {sctid: $ancestor_sctid})
    RETURN count(path) > 0 AS is_descendant
    """

    with neo4j_conn() as session:
        result = session.run(query, concept_sctid=concept_sctid, ancestor_sctid=ancestor_sctid)
        record = result.single()
        return record["is_descendant"] if record else False


def test_connection() -> bool:
    """
    Test the Neo4j connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with neo4j_conn() as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            return record["test"] == 1
    except Exception as e:
        print(f"Neo4j connection failed: {e}")
        return False


def get_snomed_stats() -> Dict[str, int]:
    """
    Get basic statistics about the SNOMED CT database.

    Returns:
        Dictionary with concept count, relationship count, etc.
    """
    stats = {}

    queries = {
        "concept_count": "MATCH (c:ObjectConcept) RETURN count(c) AS count",
        "active_concept_count": "MATCH (c:ObjectConcept {active: '1'}) RETURN count(c) AS count",
        "isa_relationship_count": "MATCH ()-[r:ISA]->() RETURN count(r) AS count",
    }

    with neo4j_conn() as session:
        for key, query in queries.items():
            result = session.run(query)
            record = result.single()
            stats[key] = record["count"] if record else 0

    return stats


# Common SNOMED CT category codes for reference
SNOMED_CATEGORIES = {
    "clinical_finding": "404684003",
    "procedure": "71388002",
    "body_structure": "123037004",
    "organism": "410607006",
    "substance": "105590001",
    "pharmaceutical_product": "373873005",
    "physical_object": "260787004",
    "event": "272379006",
    "environment": "308916002",
    "qualifier_value": "362981000",
    "observable_entity": "363787002",
    "situation": "243796009",
}


if __name__ == "__main__":
    # Test the module
    print("Testing Neo4j SNOMED CT connection...")

    if test_connection():
        print("Connection successful!")

        # Get stats
        stats = get_snomed_stats()
        print(f"\nSNOMED CT Database Stats:")
        for key, value in stats.items():
            print(f"  {key}: {value:,}")

        # Test search
        print("\nSearching for 'headache'...")
        results = snomed_search_simple("headache", limit=5)
        for r in results:
            print(f"  [{r['sctid']}] {r['fsn']}")
    else:
        print("Connection failed. Please check your Neo4j configuration.")
