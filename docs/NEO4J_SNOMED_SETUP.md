# Neo4j SNOMED CT Setup Guide

This guide explains how to set up the Neo4j SNOMED CT knowledge graph for the AI Triage Agent.

## Project Structure

```
AI_Triage_Agent/
├── app/
│   ├── graph/
│   │   ├── nodes/
│   │   │   ├── parse_symptom.py    # ← MODIFIED: Uses Neo4j SNOMED lookups
│   │   │   ├── retrieve_docs.py
│   │   │   ├── reason_reflect.py
│   │   │   ├── vote_confidence.py
│   │   │   └── fallback_route.py
│   │   └── triage_graph.py
│   ├── retriever/
│   │   ├── HybridRetriever.py
│   │   └── llama_index_retriever.py
│   ├── monitoring/
│   ├── observability/
│   ├── storage/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   └── utils.py
├── data_pipeline/
│   ├── common_db.py               # PostgreSQL connector
│   ├── neo4j_db.py                # ← NEW: Neo4j SNOMED connector
│   ├── embedder.py
│   ├── build_tbi_faiss.py
│   └── load_tbi_sample.py
├── docs/
│   └── NEO4J_SNOMED_SETUP.md      # ← NEW: This file
├── scripts/
│   └── setup_neo4j_snomed.sh      # ← NEW: Setup script
├── .env                           # ← MODIFIED: Added Neo4j config
├── requirements.txt
└── README.md
```

## Files Modified/Added

### 1. NEW: `data_pipeline/neo4j_db.py`
Neo4j connector module with SNOMED CT query functions:
- `snomed_search_simple(term)` - Search concepts by term
- `snomed_get_concept(sctid)` - Get concept by SNOMED ID
- `snomed_get_parents(sctid)` - Get parent concepts (broader terms)
- `snomed_get_children(sctid)` - Get child concepts (narrower terms)
- `snomed_get_ancestors(sctid)` - Get all ancestors up the hierarchy
- `snomed_is_descendant_of(concept, ancestor)` - Check if concept is under ancestor

### 2. MODIFIED: `app/graph/nodes/parse_symptom.py`
Updated to use Neo4j for SNOMED CT lookups:
- Primary: Neo4j SNOMED CT knowledge graph
- Fallback: PostgreSQL snomed_descriptions table
- Extracts symptom keywords and maps to SNOMED CT codes
- Retrieves concept hierarchy for better understanding

### 3. MODIFIED: `.env`
Added Neo4j configuration:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=snomed2024
NEO4J_DATABASE=neo4j
```

---

## Prerequisites

1. **Neo4j** (version 5.x or higher)
2. **Python 3.9+** with `neo4j` package
3. **SNOMED CT RF2 Release Files** (download from SNOMED International or NLM UMLS)
4. **snomed-database-loader** scripts

---

## Installation Steps

### Step 1: Install Neo4j

**macOS (Homebrew):**
```bash
brew install neo4j
```

**Linux (apt):**
```bash
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo apt install neo4j
```

**Docker:**
```bash
docker run -d \
  --name neo4j-snomed \
  -p 7474:7474 -p 7687:7687 \
  -v $HOME/neo4j/data:/data \
  -e NEO4J_AUTH=neo4j/snomed2024 \
  -e NEO4J_dbms_memory_heap_max__size=4g \
  neo4j:5
```

### Step 2: Configure Neo4j

Edit the Neo4j configuration file:

**macOS (Homebrew):** `/opt/homebrew/Cellar/neo4j/<version>/libexec/conf/neo4j.conf`
**Linux:** `/etc/neo4j/neo4j.conf`

Make these changes:
```properties
# Comment out import directory restriction (REQUIRED for SNOMED loading)
#server.directories.import=import

# Allow CSV import from file URLs
dbms.security.allow_csv_import_from_file_urls=true

# Set heap memory to 4GB (REQUIRED for SNOMED loading)
server.memory.heap.max_size=4g
```

### Step 3: Start Neo4j and Set Password

```bash
# Start Neo4j
neo4j start

# Wait for startup, then set password
cypher-shell -u neo4j -p neo4j -d system \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'snomed2024';"

# Verify connection
cypher-shell -u neo4j -p snomed2024 "RETURN 1 AS test;"
```

### Step 4: Download SNOMED CT Data

1. Go to [SNOMED International](https://www.snomed.org/) or [NLM UMLS](https://www.nlm.nih.gov/research/umls/)
2. Download the **RF2 Full Release** (e.g., `SnomedCT_USEditionRF2_PRODUCTION_*.zip`)
3. Extract to a directory (e.g., `~/SnomedCT_RF2/`)

The directory should contain:
```
SnomedCT_RF2/
├── Full/
│   ├── Terminology/
│   │   ├── sct2_Concept_Full_*.txt
│   │   ├── sct2_Description_Full-en_*.txt
│   │   └── sct2_Relationship_Full_*.txt
│   └── Refset/
└── Snapshot/
```

### Step 5: Clone snomed-database-loader

```bash
git clone https://github.com/IHTSDO/snomed-database-loader.git
cd snomed-database-loader/NEO4J

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install py2neo
```

### Step 6: Load SNOMED CT into Neo4j

```bash
cd snomed-database-loader/NEO4J
source venv/bin/activate

# Run the loader (takes 10-30 minutes)
python3 snomed_g_graphdb_build_tools.py db_build \
  --action create \
  --rf2 ~/SnomedCT_RF2/Full/ \
  --release_type full \
  --neopw snomed2024 \
  --output_dir ./output \
  --language_code 'en'
```

**Expected output:**
```
JOB_START
FIND_ROLENAMES
FIND_ROLEGROUPS
MAKE_CONCEPT_CSVS
MAKE_DESCRIPTION_CSVS
MAKE_ISA_REL_CSVS
MAKE_DEFINING_REL_CSVS
TEMPLATE_PROCESSING
CYPHER_EXECUTION
CHECK_RESULT
JOB_END
RESULT: SUCCESS
```

### Step 7: Verify the Load

```bash
# Check concept count
cypher-shell -u neo4j -p snomed2024 \
  "MATCH (c:ObjectConcept) RETURN count(c) AS concepts;"

# Expected: ~530,000+ concepts

# Test a search
cypher-shell -u neo4j -p snomed2024 \
  "MATCH (c:ObjectConcept) WHERE c.FSN CONTAINS 'headache' RETURN c.sctid, c.FSN LIMIT 5;"
```

### Step 8: Install Python Dependencies

```bash
cd ~/AI_Triage_Agent
source .venv/bin/activate
pip install neo4j python-dotenv
```

### Step 9: Update .env

Add to your `.env` file:
```bash
# Neo4j SNOMED CT Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=snomed2024
NEO4J_DATABASE=neo4j

# Enable Neo4j SNOMED (set to false to use PostgreSQL fallback)
USE_NEO4J_SNOMED=true
```

---

## Usage Examples

### Basic SNOMED Search

```python
from data_pipeline.neo4j_db import snomed_search_simple

# Search for symptoms
results = snomed_search_simple("chest pain", limit=5)
for r in results:
    print(f"[{r['sctid']}] {r['fsn']}")

# Output:
# [29857009] Chest pain (finding)
# [3368006] Dull chest pain (finding)
# [102587001] Acute chest pain (finding)
```

### Get Concept Hierarchy

```python
from data_pipeline.neo4j_db import snomed_get_parents, snomed_get_children

# Get parent concepts (broader terms)
parents = snomed_get_parents("25064002")  # Headache
for p in parents:
    print(f"Parent: [{p['sctid']}] {p['fsn']}")

# Get child concepts (narrower terms)
children = snomed_get_children("25064002")
for c in children:
    print(f"Child: [{c['sctid']}] {c['fsn']}")
```

### Check Concept Relationships

```python
from data_pipeline.neo4j_db import snomed_is_descendant_of

# Is "Migraine" a type of "Headache"?
is_migraine_headache = snomed_is_descendant_of("37796009", "25064002")
print(f"Migraine is a type of Headache: {is_migraine_headache}")
# Output: True
```

### In the Symptom Parser

The `parse_symptom.py` node automatically uses Neo4j:

```python
from app.graph.nodes.parse_symptom import parse_symptom
from app.schemas import GraphState

state = GraphState(patient_input={"text": "I have a severe headache and fever"})
result = parse_symptom(state)

for entity in result.entities:
    print(f"Symptom: {entity['symptom']}")
    print(f"SNOMED: [{entity['sctid']}] {entity['fsn']}")
```

---

## Troubleshooting

### "Cannot load from URL" error during SNOMED loading
Ensure Neo4j config has:
```properties
#server.directories.import=import
dbms.security.allow_csv_import_from_file_urls=true
```
Then restart Neo4j: `neo4j restart`

### "OutOfMemoryError" during loading
Increase heap memory in neo4j.conf:
```properties
server.memory.heap.max_size=4g
```

### Connection refused
Check if Neo4j is running:
```bash
neo4j status
# If not running:
neo4j start
```

### Wrong config file being used
Neo4j may read from multiple locations. Check:
- Homebrew: `/opt/homebrew/Cellar/neo4j/<version>/libexec/conf/neo4j.conf`
- System: `/etc/neo4j/neo4j.conf`
- User: `~/.neo4j/neo4j.conf`

---

## Data Statistics (US Edition September 2025)

| Metric | Count |
|--------|-------|
| Total Concepts | 532,287 |
| Active Concepts | 382,170 |
| Descriptions | 1,698,962 |
| ISA Relationships | 1,233,909 |
| Clinical Relationships | 3,000,000+ |

---

## Neo4j Browser

Access the visual graph explorer at: **http://localhost:7474**

Example Cypher queries:
```cypher
// Find all types of headache
MATCH (c:ObjectConcept)-[:ISA*1..3]->(parent:ObjectConcept {sctid: '25064002'})
RETURN c.sctid, c.FSN LIMIT 20;

// Find what body sites are affected by chest pain
MATCH (c:ObjectConcept {sctid: '29857009'})-[:FINDING_SITE]->(site:ObjectConcept)
RETURN site.sctid, site.FSN;

// Find related conditions
MATCH (c:ObjectConcept {sctid: '29857009'})-[r]->(related:ObjectConcept)
WHERE type(r) <> 'ISA'
RETURN type(r), related.FSN LIMIT 10;
```
