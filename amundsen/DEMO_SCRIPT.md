# Amundsen Demo Script - Data Governance Showcase

**Total Duration**: 8 minutes  
**Target Audience**: Business stakeholders, data teams, governance officers  
**Objective**: Demonstrate modern data catalog capabilities with business glossary

---

## Pre-Demo Checklist ✅

```bash
# Verify all services are running
docker-compose ps | grep -E "(amundsen|postgres|marquez)"

# Check Amundsen UI is accessible
curl -s http://localhost:5005 | grep "Amundsen"

# Verify metadata is loaded
docker exec dp_amundsen_neo4j cypher-shell -u neo4j -p test \
  "MATCH (t:Table {name: 'clean_204'}) RETURN t.name"
```

Expected output:
- ✅ 5 Amundsen containers running (healthy)
- ✅ Amundsen UI returns HTML
- ✅ Neo4j returns "clean_204"

---

## Demo Flow

### Part 1: Data Discovery (3 minutes)

**Talking Points**:
- "Modern data platforms need discovery - imagine Google for your data"
- "Our data catalog indexes all datasets, making them searchable"
- "Let me show you how easy it is to find data"

**Actions**:

1. **Open Amundsen UI**
   ```
   URL: http://localhost:5005
   ```
   - Point out clean, intuitive interface
   - Highlight search bar prominence

2. **Search for Data**
   - Type: `cell tower` or `clean_204`
   - Press Enter
   - **Expected**: Table appears in results
   
3. **Explore Table Details**
   - Click on `postgres://dataplatform.cell_towers/clean_204`
   - **Show**:
     - Table description: "47,114 cell tower installations"
     - Owner: Data Engineering Team
     - Tags: telecommunications, netherlands, production, geo-data, pii
     - Last updated information

4. **Review Statistics Panel**
   - Point to right sidebar
   - **Highlight**:
     - 📊 record_count: 47,114
     - 📊 unique_cells: 45,749  
     - 📊 data_quality: 97%
   - "This gives instant confidence in data quality"

5. **Browse Columns**
   - Scroll to columns section (14 columns)
   - **Show examples**:
     - `mcc` - Mobile Country Code (with glossary link)
     - `radio` - Radio Access Technology
     - `lat`, `lon` - marked with PII tag ⚠️

**Key Message**: "In 30 seconds, we found our data, understood its quality, and identified the owner. No more hunting through wikis or Slack!"

---

### Part 2: Business Glossary (2 minutes)

**Talking Points**:
- "Technical metadata alone isn't enough"
- "Business users need definitions in their language"
- "Our glossary bridges technical and business worlds"

**Actions**:

1. **Click on a Glossary Term**
   - In the table view, click "Mobile Country Code" link next to `mcc` column
   - **OR** search for "Mobile Country Code" in main search
   
2. **Show Glossary Term Details**
   - **Read definition**: "A three-digit code assigned by ITU-T E.212..."
   - **Show example**: "204 = Netherlands"
   - **Point to standard**: "ITU-T E.212 (official telecom standard)"
   - **Show domain**: "Telecommunications"

3. **Demonstrate Term Relationships**
   - Show related terms graph (if available in UI)
   - Or explain: "This term relates to Cell Tower, which uses RAT"
   - Visual representation of concept connections

4. **Show Other Glossary Terms**
   - Quickly browse to:
     - "Cell Tower" - infrastructure definition
     - "Geographic Coordinates" - with GDPR sensitivity note
     - "Signal Strength" - with dBm examples
   
5. **Highlight Business Value**
   - "New team members understand data instantly"
   - "Consistent definitions across organization"
   - "Compliance documentation built-in (GDPR notes)"

**Key Message**: "Our glossary turns cryptic column names into business concepts everyone understands."

---

### Part 3: Data Governance (2 minutes)

**Talking Points**:
- "Governance isn't just compliance - it's trust"
- "We need to know: What is sensitive? Who owns it? Is it quality?"
- "Let's see governance in action"

**Actions**:

1. **Show PII Tag**
   - Back to table view: `clean_204`
   - Point to `lat` and `lon` columns
   - **Show**: Red "pii" tag on both
   - "Immediately visible - these columns need special handling"

2. **Click into PII Column**
   - Click on `lon` or `lat` column
   - **Read description**: "⚠️ SENSITIVE: Contains precise location data subject to GDPR"
   - Link to glossary term with sensitivity notes

3. **Discuss Compliance**
   - "Geographic Coordinates" glossary term
   - **Show**: "Sensitivity: PII - Subject to GDPR Article 4(1)"
   - "Built into our documentation, not separate"

4. **Review Ownership**
   - Scroll to "Owners" section
   - **Show**: Data Engineering Team
   - Click owner to see their other datasets
   - "Clear accountability - no orphan datasets"

5. **Quality Metrics**
   - Return to statistics panel
   - **Emphasize**: 97% data quality
   - "Tracked over time, alerts on degradation"

6. **Tags for Organization**
   - Point to tag cloud: telecommunications, netherlands, production, geo-data, pii
   - "Filter datasets by domain, sensitivity, or use case"

**Key Message**: "Governance is embedded in discovery. Users see sensitivity, ownership, and quality immediately - no separate tool needed."

---

### Part 4: Lineage & Context (1 minute)

**Talking Points**:
- "Data doesn't exist in isolation"
- "Understanding the journey builds confidence"

**Actions**:

1. **Discuss Data Flow** (use diagram or explain):
   ```
   Google Cloud Storage → MinIO (Data Lake) → ETL Pipeline → PostgreSQL → Amundsen
   ```

2. **Mention Marquez Integration**
   - "For technical lineage, we have Marquez"
   - "Automatic tracking via OpenLineage"
   - "Amundsen shows 'what', Marquez shows 'how'"

3. **Show Programmatic Description**
   - In table view, look for "Quality Report" section
   - **Read**: "97% quality score... all records validated for geographic coordinates"
   - "Generated by our ETL pipeline"

**Key Message**: "Amundsen documents the business view, integrated with technical tools for complete picture."

---

## Demo Wrap-Up (30 seconds)

**Summary Points**:
1. ✅ **Discovery**: Found data in seconds with powerful search
2. ✅ **Business Context**: Glossary bridges tech and business language
3. ✅ **Governance**: PII tags, ownership, quality - all visible
4. ✅ **Integration**: Works with existing tools (Marquez, Superset)

**Call to Action**:
- "This is production-ready - our real data, real definitions"
- "Team can start using immediately"
- "Let's discuss rollout to other datasets"

---

## Q&A Preparation

### Expected Questions & Answers

**Q: How do we keep metadata up to date?**  
A: Automated sync via databuilder runs nightly. ETL pipelines update stats. Manual glossary reviews quarterly.

**Q: Can we integrate with [other tool]?**  
A: Yes - Amundsen has APIs. We already integrate Marquez (lineage) and can add Superset (BI), Airflow (scheduling), etc.

**Q: What about access control?**  
A: Amundsen supports LDAP/OAuth. We can sync with existing permissions. Discovery doesn't grant data access.

**Q: How much effort to add more datasets?**  
A: Automated for PostgreSQL, Trino, S3. Run extractor script → instant catalog. Maybe 1 hour per data source.

**Q: What's the difference vs a wiki?**  
A: Living documentation. Stats update automatically. Searchable like Google. Integrated with data tools. Wiki gets outdated fast.

**Q: Can business users contribute?**  
A: Yes! Glossary terms can be created via UI or API. Crowdsourcing knowledge encouraged.

**Q: What about data lineage?**  
A: Marquez handles technical lineage (automatic). Amundsen shows conceptual lineage (manual). Both available.

---

## Troubleshooting During Demo

### Amundsen UI not loading
```bash
docker-compose --profile amundsen restart amundsen-frontend
# Wait 30 seconds, retry
```

### Search returns no results
```bash
# Rebuild search index
docker exec dp_amundsen_search curl -X POST http://localhost:5000/reindex
```

### Glossary terms missing
```bash
# Re-run glossary creation
python3 amundsen/create_glossary.py
```

### Neo4j connection issues
```bash
# Check Neo4j health
docker logs dp_amundsen_neo4j --tail 20
# Restart if needed
docker-compose restart amundsen-neo4j
```

---

## Post-Demo Next Steps

1. **Immediate** (Week 1):
   - Grant team access to Amundsen UI
   - Share this demo script for self-service
   - Schedule glossary review sessions

2. **Short-term** (Month 1):
   - Add 5 more critical datasets
   - Expand glossary to 20 terms
   - Set up nightly metadata sync

3. **Medium-term** (Quarter 1):
   - Integrate with Superset dashboards
   - Add Airflow DAG metadata
   - Implement role-based access control
   - Train power users as "data stewards"

4. **Long-term** (Year 1):
   - Catalog all production datasets (target: 100+)
   - Build comprehensive glossary (target: 200+ terms)
   - Establish data governance council
   - Measure adoption metrics (searches/day, active users)

---

## Success Metrics

Track these to measure impact:

- **Adoption**: Daily active users, searches per day
- **Efficiency**: Time to find data (baseline vs now)
- **Quality**: % datasets with complete metadata
- **Governance**: % PII tagged, datasets with owners
- **Satisfaction**: User surveys (quarterly)

**Target for Month 3**:
- 50+ active users per week
- 80% of datasets with complete metadata
- 100% PII columns tagged
- 100% datasets with assigned owners
- 4.5/5 user satisfaction score

---

## Additional Resources

- **Amundsen Docs**: https://www.amundsen.io/
- **Our Setup Guide**: `amundsen/README.md`
- **Metadata Scripts**: `amundsen/databuilder_ingestion.py`
- **Glossary Creator**: `amundsen/create_glossary.py`
- **Main Platform Docs**: `README.md`

---

**Demo prepared by**: Data Engineering Team  
**Last updated**: 11 October 2025  
**Version**: 1.0  
**Questions?**: #data-platform Slack channel
