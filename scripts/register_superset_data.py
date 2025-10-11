#!/usr/bin/env python3
"""
Handmatig script om PostgreSQL database en cell_towers dataset te registreren in Superset.
"""
import requests
import json
import sys

SUPERSET_URL = "http://localhost:8088"
USERNAME = "admin"
PASSWORD = "admin"

def get_session():
    """Login en krijg session met CSRF token"""
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": SUPERSET_URL,
    })
    
    # Login
    print("🔐 Logging in...")
    r = s.post(f"{SUPERSET_URL}/api/v1/security/login", json={
        "username": USERNAME,
        "password": PASSWORD,
        "provider": "db",
        "refresh": True
    })
    r.raise_for_status()
    
    data = r.json()
    access_token = data.get("access_token") or data.get("result", {}).get("access_token")
    if not access_token:
        raise RuntimeError(f"No access token: {r.text}")
    
    s.headers["Authorization"] = f"Bearer {access_token}"
    
    # Get CSRF token
    r = s.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    r.raise_for_status()
    csrf = r.json()["result"]
    s.headers["X-CSRFToken"] = csrf
    
    print("✅ Logged in successfully")
    return s

def get_or_create_database(session):
    """Maak PostgreSQL database connectie aan"""
    print("\n📊 Checking for PostgreSQL database...")
    
    # Check bestaande databases
    r = session.get(f"{SUPERSET_URL}/api/v1/database/")
    r.raise_for_status()
    dbs = r.json().get("result", [])
    
    for db in dbs:
        if "postgres" in db.get("database_name", "").lower():
            print(f"✅ PostgreSQL database already exists: {db['database_name']} (ID: {db['id']})")
            return db['id']
    
    # Maak nieuwe database aan
    print("📝 Creating PostgreSQL database connection...")
    uri = "postgresql+psycopg2://superset:superset@postgres:5432/superset"
    
    payload = {
        "database_name": "Postgres",
        "sqlalchemy_uri": uri,
        "expose_in_sqllab": True,
        "allow_csv_upload": True,
        "allow_run_async": False,
        "allow_ctas": False,
        "allow_cvas": False,
        "impersonate_user": False,
        "extra": "{}",
    }
    
    r = session.post(f"{SUPERSET_URL}/api/v1/database/", json=payload)
    if r.status_code in (200, 201):
        db_id = r.json()["id"]
        print(f"✅ PostgreSQL database created (ID: {db_id})")
        return db_id
    
    raise RuntimeError(f"Failed to create database: {r.status_code} {r.text}")

def get_or_create_dataset(session, database_id):
    """Registreer cell_towers.clean_204 dataset"""
    print("\n📋 Checking for cell_towers.clean_204 dataset...")
    
    # Check bestaande datasets
    filters = json.dumps({
        "filters": [
            {"col": "table_name", "opr": "eq", "value": "clean_204"},
            {"col": "schema", "opr": "eq", "value": "cell_towers"}
        ]
    })
    
    r = session.get(f"{SUPERSET_URL}/api/v1/dataset/", params={"q": filters})
    r.raise_for_status()
    
    if r.json().get("count", 0) > 0:
        dataset = r.json()["result"][0]
        print(f"✅ Dataset already exists: cell_towers.clean_204 (ID: {dataset['id']})")
        return dataset['id']
    
    # Get user ID
    r = session.get(f"{SUPERSET_URL}/api/v1/me/")
    r.raise_for_status()
    user_id = r.json().get("id")
    
    # Maak dataset aan
    print("📝 Creating cell_towers.clean_204 dataset...")
    payload = {
        "database": database_id,
        "schema": "cell_towers",
        "table_name": "clean_204",
        "owners": [user_id] if user_id else []
    }
    
    r = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if r.status_code in (200, 201):
        dataset_id = r.json()["id"]
        print(f"✅ Dataset created (ID: {dataset_id})")
        return dataset_id
    
    raise RuntimeError(f"Failed to create dataset: {r.status_code} {r.text}")

def main():
    try:
        session = get_session()
        db_id = get_or_create_database(session)
        dataset_id = get_or_create_dataset(session, db_id)
        
        print("\n" + "="*60)
        print("🎉 SUCCESS!")
        print("="*60)
        print(f"\n✅ PostgreSQL database: ID {db_id}")
        print(f"✅ Dataset cell_towers.clean_204: ID {dataset_id}")
        print(f"\n🌐 Open Superset: {SUPERSET_URL}")
        print("📊 Go to: Data → Datasets → cell_towers.clean_204")
        print("🎨 Click 'Create Chart' to start visualizing!")
        print("\n💡 Example query in SQL Lab:")
        print("   SELECT radio, COUNT(*) FROM cell_towers.clean_204 GROUP BY radio;")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
