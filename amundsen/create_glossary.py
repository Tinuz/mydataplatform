#!/usr/bin/env python3
"""
Create Business Glossary Terms in Amundsen
Define key telecommunications business terms
"""

from neo4j import GraphDatabase
import sys

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test"

def create_glossary():
    """Create business glossary terms and link to columns"""
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        print("=== Creating Business Glossary in Amundsen ===\n")
        
        # Define glossary terms
        terms = [
            {
                "name": "Mobile Country Code",
                "key": "mobile_country_code",
                "definition": "A three-digit code assigned by ITU-T E.212 to uniquely identify a mobile network's country of operation. Used in conjunction with Mobile Network Code to form the Mobile Network Identity.",
                "example": "204 = Netherlands, 310 = United States, 262 = Germany",
                "standard": "ITU-T E.212",
                "domain": "Telecommunications",
                "linked_columns": ["mcc"]
            },
            {
                "name": "Cell Tower",
                "key": "cell_tower",
                "definition": "A site where antennas and electronic communications equipment are placed to create a cell in a cellular network. Provides radio coverage for mobile devices in a specific geographic area.",
                "example": "A tower with multiple antennas serving different frequencies and carriers",
                "standard": "3GPP TS 23.002",
                "domain": "Telecommunications Infrastructure",
                "linked_columns": ["cell"]
            },
            {
                "name": "Radio Access Technology",
                "key": "radio_access_technology",
                "definition": "The underlying physical connection method for a radio-based communication network. Determines the data speed, latency, and capabilities of the mobile connection.",
                "example": "GSM (2G), UMTS (3G), LTE (4G), NR (5G)",
                "standard": "3GPP specifications",
                "domain": "Telecommunications",
                "linked_columns": ["radio"]
            },
            {
                "name": "Geographic Coordinates",
                "key": "geographic_coordinates",
                "definition": "WGS84 latitude and longitude values that specify a precise location on Earth's surface. Expressed in decimal degrees with precision to approximately 1 meter.",
                "example": "Amsterdam: 52.3676° N, 4.9041° E",
                "standard": "ISO 6709 / WGS84",
                "domain": "Geospatial",
                "sensitivity": "PII - Subject to GDPR Article 4(1)",
                "linked_columns": ["lat", "lon"]
            },
            {
                "name": "Signal Strength",
                "key": "signal_strength",
                "definition": "Received signal power measured in dBm (decibels-milliwatts). Indicates the quality of the radio connection between a mobile device and cell tower. More negative values indicate weaker signals.",
                "example": "-50 dBm (excellent), -75 dBm (good), -100 dBm (poor), -110 dBm (very poor)",
                "standard": "IEEE 802.11",
                "domain": "Telecommunications",
                "linked_columns": ["averagesignal"]
            }
        ]
        
        # Create each glossary term
        for i, term in enumerate(terms, 1):
            print(f"{i}. Creating glossary term: {term['name']}")
            
            # Create the term node
            query_parts = [
                "MERGE (term:Glossary_Term {key: $term_key})",
                "ON CREATE SET",
                "  term.name = $name,",
                "  term.definition = $definition,",
                "  term.example = $example,",
                "  term.standard = $standard,",
                "  term.domain = $domain"
            ]
            
            params = {
                "term_key": f"glossary://{term['key']}",
                "name": term["name"],
                "definition": term["definition"],
                "example": term["example"],
                "standard": term["standard"],
                "domain": term["domain"]
            }
            
            # Add sensitivity if present
            if "sensitivity" in term:
                query_parts.append(",  term.sensitivity = $sensitivity")
                params["sensitivity"] = term["sensitivity"]
            
            session.run("\n".join(query_parts), **params)
            
            # Link term to relevant columns
            for col_name in term["linked_columns"]:
                session.run("""
                    MATCH (term:Glossary_Term {key: $term_key})
                    MATCH (col:Column {key: $col_key})
                    MERGE (col)-[:DEFINED_BY]->(term)
                """, 
                term_key=f"glossary://{term['key']}",
                col_key=f'postgres://dataplatform.cell_towers/clean_204/{col_name}')
                print(f"   ✓ Linked to column: {col_name}")
            
            print(f"   📖 {term['definition'][:80]}...")
            print()
        
        # Create cross-references between terms
        print("6. Creating term relationships...")
        session.run("""
            MATCH (mcc:Glossary_Term {key: 'glossary://mobile_country_code'})
            MATCH (tower:Glossary_Term {key: 'glossary://cell_tower'})
            MERGE (mcc)-[:RELATED_TO {relationship: 'identifies network of'}]->(tower)
        """)
        print("   ✓ Mobile Country Code → Cell Tower")
        
        session.run("""
            MATCH (rat:Glossary_Term {key: 'glossary://radio_access_technology'})
            MATCH (tower:Glossary_Term {key: 'glossary://cell_tower'})
            MERGE (rat)-[:RELATED_TO {relationship: 'technology used by'}]->(tower)
        """)
        print("   ✓ Radio Access Technology → Cell Tower")
        
        session.run("""
            MATCH (geo:Glossary_Term {key: 'glossary://geographic_coordinates'})
            MATCH (tower:Glossary_Term {key: 'glossary://cell_tower'})
            MERGE (geo)-[:RELATED_TO {relationship: 'locates'}]->(tower)
        """)
        print("   ✓ Geographic Coordinates → Cell Tower")
        
        session.run("""
            MATCH (signal:Glossary_Term {key: 'glossary://signal_strength'})
            MATCH (tower:Glossary_Term {key: 'glossary://cell_tower'})
            MERGE (signal)-[:RELATED_TO {relationship: 'measured from'}]->(tower)
        """)
        print("   ✓ Signal Strength → Cell Tower")
        
        # Add glossary owner
        print("\n7. Setting glossary ownership...")
        for term in terms:
            session.run("""
                MATCH (term:Glossary_Term {key: $term_key})
                MERGE (user:User {key: 'data-governance@company.com'})
                ON CREATE SET
                    user.email = 'data-governance@company.com',
                    user.first_name = 'Data Governance',
                    user.last_name = 'Team',
                    user.full_name = 'Data Governance Team'
                MERGE (term)-[:OWNED_BY]->(user)
            """, term_key=f"glossary://{term['key']}")
        print("   ✓ Owner: Data Governance Team")
        
        print("\n✅ Business Glossary successfully created!")
        print(f"\n📚 Summary:")
        print(f"   • Glossary Terms: {len(terms)}")
        print(f"   • Term Relationships: 4")
        print(f"   • Columns Linked: {sum(len(t['linked_columns']) for t in terms)}")
        print(f"\nTerms created:")
        for term in terms:
            print(f"   • {term['name']} ({term['domain']})")
        print(f"\n🌐 View in Amundsen UI: http://localhost:5005")
        print(f"💡 Search for table 'clean_204' to see glossary terms linked to columns")
        
    driver.close()
    return True

if __name__ == "__main__":
    try:
        success = create_glossary()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Metadata has been loaded: python3 amundsen/databuilder_ingestion.py")
        print("  2. Neo4j is accessible: curl http://localhost:7474")
        sys.exit(1)
