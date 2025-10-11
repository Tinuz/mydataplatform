# DataHub Setup voor Modern Data Platform

## Waarom DataHub?

DataHub voegt toe wat Marquez mist:
- ✅ **Data Glossary** - Business terms en definities
- ✅ **Data Dictionary** - Centralized metadata
- ✅ **Rich UI** - Search, browse, discover
- ✅ **Tags & Ownership** - Better governance
- ✅ **Impact Analysis** - Downstream dependencies
- ✅ **API-first** - GraphQL + REST

## Architectuur

```
DataHub Frontend (Port 9002)
    ↓
DataHub GMS (Port 8081) - Metadata service
    ↓
MySQL (metadata) + Elasticsearch (search) + Neo4j (lineage graph)
```

## Demo Features

### 1. Data Glossary
Definieer business terms:
- **MCC** = Mobile Country Code - Identifies the country
- **Cell Tower** = Physical telecommunications infrastructure
- **Radio Type** = Technology standard (GSM, LTE, 5G)

### 2. Dataset Documentation
- Column descriptions
- Sample data
- Data quality metrics
- Usage statistics

### 3. Lineage Visualization
- Better dan Marquez: interactive graph
- Impact analysis: welke dashboards gebruiken deze data?

### 4. Data Discovery
- Full-text search over alle metadata
- Filter op tags, owners, domains

## Integration met Bestaande Platform

DataHub zal:
- Parallel draaien naast Marquez (niet vervangen)
- PostgreSQL metadata automatisch ingest
- Trino catalog metadata importeren
- Superset datasets linken

## Resource Requirements

- Memory: +2GB
- Storage: +500MB
- Ports: 9002 (UI), 8081 (API conflicteert met Swagger!)

## Next Steps

1. Add DataHub quickstart to docker-compose
2. Ingest PostgreSQL metadata
3. Create glossary terms
4. Link to existing datasets
5. Demo script aanpassen
