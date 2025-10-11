# Amundsen Data Catalog

Amundsen is a data discovery and metadata engine developed by Lyft. It provides:
- Data discovery and search
- Column-level metadata
- Data lineage visualization
- User and team ownership
- **Business glossary** capabilities

## Quick Start

### Start Amundsen
```bash
docker-compose --profile amundsen up -d
```

### Access Points
- **Amundsen UI**: http://localhost:5005
- **Neo4j Browser**: http://localhost:7474 (user: `neo4j`, pass: `test`)
- **Metadata API**: http://localhost:5002
- **Search API**: http://localhost:5001

### Stop Amundsen
```bash
docker-compose --profile amundsen down
```

## Architecture

Amundsen consists of 5 services:

1. **Frontend** (Port 5005): React-based web UI
2. **Metadata** (Port 5002): Metadata service (uses Neo4j)
3. **Search** (Port 5001): Search service (uses Elasticsearch)
4. **Neo4j** (Ports 7474/7687): Graph database for metadata
5. **Elasticsearch** (Port 9200): Search index

## Adding Data to Amundsen

### Method 1: Manual via UI
1. Open http://localhost:5005
2. Click "Add Table" or use the search
3. Enter table details manually

### Method 2: Via Databuilder (Recommended)

Install amundsen-databuilder:
```bash
pip install amundsen-databuilder
```

Create an ingestion script:
```python
from pyhocon import ConfigFactory
from databuilder.extractor.postgres_metadata_extractor import PostgresMetadataExtractor
from databuilder.job.job import DefaultJob
from databuilder.loader.file_system_neo4j_csv_loader import FsNeo4jCSVLoader
from databuilder.publisher.neo4j_csv_publisher import Neo4jCsvPublisher
from databuilder.task.task import DefaultTask

# Configure PostgreSQL connection
conf = ConfigFactory.from_dict({
    'extractor.postgres_metadata.{}'.format(PostgresMetadataExtractor.WHERE_CLAUSE_SUFFIX_KEY):
        "table_schema = 'cell_towers'",
    'extractor.postgres_metadata.{}'.format(PostgresMetadataExtractor.USE_CATALOG_AS_CLUSTER_NAME):
        True,
    'extractor.postgres_metadata.extractor.sqlalchemy.{}'.format(PostgresMetadataExtractor.DATABASE_KEY):
        'postgresql://superset:superset@localhost:5432/superset',
})

# Run extraction job
job = DefaultJob(
    conf=conf,
    task=DefaultTask(
        extractor=PostgresMetadataExtractor(),
        loader=FsNeo4jCSVLoader()
    ),
    publisher=Neo4jCsvPublisher()
)
job.launch()
```

### Method 3: Neo4j Cypher Queries

Open Neo4j Browser (http://localhost:7474) and run:

```cypher
// Create table node
CREATE (t:Table {
  name: 'clean_204',
  database: 'postgres',
  cluster: 'dataplatform', 
  schema: 'cell_towers',
  description: 'Cleaned cell tower data for Netherlands'
})

// Create column nodes
CREATE (c1:Column {
  name: 'mcc',
  type: 'INTEGER',
  sort_order: 0,
  description: 'Mobile Country Code - Always 204 for Netherlands'
})

// Link column to table
CREATE (t)-[:COLUMN]->(c1)

// Add tags
CREATE (tag:Tag {tag_name: 'telecommunications'})
CREATE (t)-[:TAGGED_BY]->(tag)
```

## Our Cell Tower Dataset

**Table**: `postgres://dataplatform/cell_towers/clean_204`

**Statistics**:
- 47,114 total records
- 45,749 unique cells
- Data quality: 97%

**Columns** (14 total):
1. `radio` - Radio Access Technology (GSM/UMTS/LTE/NR)
2. `mcc` - Mobile Country Code (204 = Netherlands)
3. `net` - Mobile Network Code (carrier identifier)
4. `area` - Location Area Code
5. `cell` - Cell ID (unique identifier)
6. `unit` - Unit identifier
7. `lon` - Longitude (WGS84) ⚠️ PII
8. `lat` - Latitude (WGS84) ⚠️ PII  
9. `range` - Coverage range (meters)
10. `samples` - Measurement samples
11. `changeable` - Location changeability flag
12. `created` - Creation timestamp
13. `updated` - Update timestamp
14. `averagesignal` - Signal strength (dBm)

**Tags**: telecommunications, netherlands, production, geo-data, pii

**Owner**: Data Engineering Team

## Demo Flow (8 minutes)

### 1. Data Discovery (3 min)
- Open Amundsen UI
- Search for "cell" or "tower"
- Browse table details
- View column metadata
- Check data freshness

### 2. Business Glossary (2 min)
- Create glossary term for "Mobile Country Code"
- Link to ITU-T E.212 standard
- Associate with `mcc` column
- Add business context

### 3. Governance (2 min)
- Review PII tags on lat/lon columns
- Check data ownership
- View data quality metrics
- Document compliance notes (GDPR)

### 4. Lineage (1 min)
- Trace data from GCS → MinIO → PostgreSQL
- View upstream/downstream dependencies
- Check ETL job metadata

## Business Glossary Examples

Here are 5 key business terms for our telecom data:

### 1. Mobile Country Code (MCC)
**Definition**: A three-digit code assigned by ITU-T E.212 to uniquely identify a mobile network's country.  
**Example**: 204 = Netherlands  
**Standard**: ITU-T E.212  
**Related Columns**: `cell_towers.clean_204.mcc`

### 2. Cell Tower
**Definition**: A site where antennas and electronic communications equipment are placed to create a cell in a cellular network.  
**Business Context**: Critical infrastructure for mobile telecommunications  
**Related Tables**: `cell_towers.clean_204`

### 3. Radio Access Technology (RAT)
**Definition**: The underlying physical connection method for a radio-based communication network.  
**Values**: GSM (2G), UMTS (3G), LTE (4G), NR (5G)  
**Standard**: 3GPP specifications  
**Related Columns**: `cell_towers.clean_204.radio`

### 4. Geographic Coordinates
**Definition**: WGS84 latitude and longitude values for precise location.  
**Sensitivity**: Contains PII - subject to GDPR  
**Format**: ISO 6709  
**Related Columns**: `cell_towers.clean_204.lat`, `cell_towers.clean_204.lon`

### 5. Signal Strength
**Definition**: Received signal power measured in dBm (decibels-milliwatts).  
**Range**: Typically -50 dBm (excellent) to -110 dBm (poor)  
**Standard**: IEEE 802.11  
**Related Columns**: `cell_towers.clean_204.averagesignal`

## Amundsen vs Marquez

| Feature | Amundsen | Marquez |
|---------|----------|---------|
| **Primary Focus** | Data Discovery & Catalog | Data Lineage & Observability |
| **UI Complexity** | Rich, user-friendly | Simple, developer-focused |
| **Business Glossary** | ✅ Yes | ❌ No |
| **Column-level Metadata** | ✅ Extensive | ⚠️ Basic |
| **Data Lineage** | ⚠️ Manual/Basic | ✅ Automatic via OpenLineage |
| **Search** | ✅ Powerful (Elasticsearch) | ⚠️ Basic |
| **User Management** | ✅ Teams & Owners | ❌ No |
| **API Integration** | REST APIs | OpenLineage API |
| **Setup Complexity** | Medium (5 services) | Low (2 services) |
| **Memory Usage** | ~2GB | ~500MB |

## When to Use What

### Use Amundsen for:
- Data discovery and search
- Business glossary and definitions
- Column-level documentation
- Data governance and ownership
- User-facing data catalog

### Use Marquez for:
- Automated lineage tracking
- ETL job monitoring
- Pipeline observability
- Developer-focused lineage
- OpenLineage integration

### Use Both Together:
- Amundsen: Business context and discovery
- Marquez: Technical lineage and monitoring
- Complementary tools, not competitors

## Troubleshooting

### Services won't start
```bash
# Check logs
docker logs dp_amundsen_frontend
docker logs dp_amundsen_metadata
docker logs dp_amundsen_search

# Restart services
docker-compose --profile amundsen restart
```

### Neo4j connection issues
```bash
# Test Neo4j
docker exec dp_amundsen_neo4j cypher-shell -u neo4j -p test "RETURN 1"

# Check Neo4j logs
docker logs dp_amundsen_neo4j
```

### Elasticsearch not responding
```bash
# Check Elasticsearch health
curl http://localhost:9200/_cluster/health

# Restart Elasticsearch
docker-compose restart amundsen-elasticsearch
```

### Frontend can't reach backend
```bash
# Verify network
docker network inspect data-platform_default

# Check service connectivity
docker exec dp_amundsen_frontend curl http://amundsen-metadata:5000/healthcheck
```

## Resources

- **Amundsen Documentation**: https://www.amundsen.io/amundsen/
- **GitHub**: https://github.com/amundsen-io/amundsen
- **Databuilder Guide**: https://www.amundsen.io/amundsen/databuilder/
- **Neo4j Query Language**: https://neo4j.com/docs/cypher-manual/current/
- **OpenLineage Integration**: https://openlineage.io/

## Next Steps

1. ✅ Amundsen is running
2. ⏳ Ingest cell tower metadata using databuilder
3. ⏳ Create business glossary terms
4. ⏳ Set up automated metadata sync
5. ⏳ Configure user authentication
6. ⏳ Integrate with existing tools (Superset, Marquez)
