#!/bin/bash
#
# Neo4j SNOMED CT Setup Script for AI Triage Agent
# =================================================
# This script automates the setup of Neo4j with SNOMED CT data.
#
# Prerequisites:
#   - Neo4j installed (brew install neo4j OR docker)
#   - SNOMED CT RF2 files downloaded
#   - snomed-database-loader cloned
#
# Usage:
#   ./setup_neo4j_snomed.sh --rf2 /path/to/SnomedCT/Full --loader /path/to/snomed-database-loader/NEO4J
#

set -e

# Default values
NEO4J_PASSWORD="snomed2024"
NEO4J_USER="neo4j"
LANGUAGE_CODE="en"
OUTPUT_DIR="./output"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "Usage: $0 --rf2 <path-to-rf2-full> --loader <path-to-snomed-loader>"
    echo ""
    echo "Options:"
    echo "  --rf2       Path to SNOMED CT RF2 Full directory (contains Terminology folder)"
    echo "  --loader    Path to snomed-database-loader/NEO4J directory"
    echo "  --password  Neo4j password (default: snomed2024)"
    echo "  --lang      Language code (default: en)"
    echo "  --help      Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --rf2 ~/SnomedCT_RF2/Full --loader ~/snomed-database-loader/NEO4J"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rf2)
            RF2_PATH="$2"
            shift 2
            ;;
        --loader)
            LOADER_PATH="$2"
            shift 2
            ;;
        --password)
            NEO4J_PASSWORD="$2"
            shift 2
            ;;
        --lang)
            LANGUAGE_CODE="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$RF2_PATH" ] || [ -z "$LOADER_PATH" ]; then
    print_error "Missing required arguments"
    usage
fi

# Validate paths
if [ ! -d "$RF2_PATH/Terminology" ]; then
    print_error "RF2 path does not contain Terminology folder: $RF2_PATH"
    exit 1
fi

if [ ! -f "$LOADER_PATH/snomed_g_graphdb_build_tools.py" ]; then
    print_error "Loader path does not contain snomed_g_graphdb_build_tools.py: $LOADER_PATH"
    exit 1
fi

echo "=============================================="
echo "Neo4j SNOMED CT Setup"
echo "=============================================="
echo "RF2 Path: $RF2_PATH"
echo "Loader Path: $LOADER_PATH"
echo "Neo4j Password: $NEO4J_PASSWORD"
echo "Language: $LANGUAGE_CODE"
echo "=============================================="
echo ""

# Step 1: Check Neo4j installation
print_step "Checking Neo4j installation..."
if ! command -v neo4j &> /dev/null; then
    print_error "Neo4j not found. Please install Neo4j first."
    echo "  macOS: brew install neo4j"
    echo "  Linux: sudo apt install neo4j"
    exit 1
fi
NEO4J_VERSION=$(neo4j --version 2>/dev/null || echo "unknown")
echo "  Neo4j version: $NEO4J_VERSION"

# Step 2: Configure Neo4j
print_step "Configuring Neo4j..."

# Find neo4j.conf
if [ -f "/opt/homebrew/Cellar/neo4j/*/libexec/conf/neo4j.conf" ]; then
    NEO4J_CONF=$(ls /opt/homebrew/Cellar/neo4j/*/libexec/conf/neo4j.conf 2>/dev/null | head -1)
elif [ -f "/etc/neo4j/neo4j.conf" ]; then
    NEO4J_CONF="/etc/neo4j/neo4j.conf"
else
    print_warn "Could not find neo4j.conf automatically"
    echo "  Please manually configure neo4j.conf with:"
    echo "    #server.directories.import=import"
    echo "    dbms.security.allow_csv_import_from_file_urls=true"
    echo "    server.memory.heap.max_size=4g"
    NEO4J_CONF=""
fi

if [ -n "$NEO4J_CONF" ]; then
    echo "  Config file: $NEO4J_CONF"

    # Backup original config
    cp "$NEO4J_CONF" "${NEO4J_CONF}.backup.$(date +%Y%m%d%H%M%S)"

    # Comment out import directory restriction
    sed -i.bak 's/^server.directories.import=import/#server.directories.import=import/' "$NEO4J_CONF"

    # Add required settings if not present
    if ! grep -q "dbms.security.allow_csv_import_from_file_urls=true" "$NEO4J_CONF"; then
        echo "dbms.security.allow_csv_import_from_file_urls=true" >> "$NEO4J_CONF"
    fi

    if ! grep -q "server.memory.heap.max_size=4g" "$NEO4J_CONF"; then
        echo "server.memory.heap.max_size=4g" >> "$NEO4J_CONF"
    fi

    echo "  Configuration updated"
fi

# Step 3: Start Neo4j
print_step "Starting Neo4j..."
neo4j status &>/dev/null && neo4j stop &>/dev/null
sleep 2
neo4j start
echo "  Waiting for Neo4j to start..."
sleep 10

# Step 4: Set password
print_step "Setting Neo4j password..."
echo "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO '$NEO4J_PASSWORD';" | \
    cypher-shell -u neo4j -p neo4j -d system 2>/dev/null || \
    echo "  Password already set or using existing password"

# Verify connection
if echo "RETURN 1;" | cypher-shell -u neo4j -p "$NEO4J_PASSWORD" &>/dev/null; then
    echo "  Connection verified"
else
    print_error "Could not connect to Neo4j with password: $NEO4J_PASSWORD"
    exit 1
fi

# Step 5: Setup Python environment for loader
print_step "Setting up Python environment..."
cd "$LOADER_PATH"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q py2neo
echo "  Python environment ready"

# Step 6: Clear existing data (optional)
print_step "Clearing existing SNOMED data..."
echo "MATCH (n) DETACH DELETE n;" | cypher-shell -u neo4j -p "$NEO4J_PASSWORD" 2>/dev/null || true
echo "  Database cleared"

# Step 7: Load SNOMED CT
print_step "Loading SNOMED CT data (this may take 10-30 minutes)..."
mkdir -p "$OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"/*

python3 snomed_g_graphdb_build_tools.py db_build \
    --action create \
    --rf2 "$RF2_PATH" \
    --release_type full \
    --neopw "$NEO4J_PASSWORD" \
    --output_dir "$OUTPUT_DIR" \
    --language_code "$LANGUAGE_CODE"

# Step 8: Verify load
print_step "Verifying SNOMED CT load..."
CONCEPT_COUNT=$(echo "MATCH (c:ObjectConcept) RETURN count(c) AS count;" | \
    cypher-shell -u neo4j -p "$NEO4J_PASSWORD" 2>/dev/null | tail -1)
ISA_COUNT=$(echo "MATCH ()-[r:ISA]->() RETURN count(r) AS count;" | \
    cypher-shell -u neo4j -p "$NEO4J_PASSWORD" 2>/dev/null | tail -1)

echo ""
echo "=============================================="
echo "SNOMED CT Load Complete!"
echo "=============================================="
echo "Concepts loaded: $CONCEPT_COUNT"
echo "ISA relationships: $ISA_COUNT"
echo ""
echo "Neo4j Browser: http://localhost:7474"
echo "Bolt URI: bolt://localhost:7687"
echo "Username: neo4j"
echo "Password: $NEO4J_PASSWORD"
echo "=============================================="
echo ""
echo "Add to your .env file:"
echo "  NEO4J_URI=bolt://localhost:7687"
echo "  NEO4J_USER=neo4j"
echo "  NEO4J_PASSWORD=$NEO4J_PASSWORD"
echo "  NEO4J_DATABASE=neo4j"
echo ""
