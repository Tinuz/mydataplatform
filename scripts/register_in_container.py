#!/usr/bin/env python3
"""
Script om PostgreSQL database en dataset te registreren in Superset.
Draait BINNEN de Superset container, dus heeft toegang tot alle packages.
"""
import sys
sys.path.insert(0, '/app')

from superset import db, security_manager
from superset.models.core import Database
from flask import g

# Flask app context nodig
from superset.app import create_app
app = create_app()

with app.app_context():
    # 1. Check of PostgreSQL database al bestaat
    existing_db = db.session.query(Database).filter(
        Database.database_name == 'Postgres'
    ).first()
    
    if existing_db:
        print(f"✅ PostgreSQL database already exists (ID: {existing_db.id})")
        db_id = existing_db.id
    else:
        # Maak nieuwe database aan
        print("📝 Creating PostgreSQL database connection...")
        new_db = Database(
            database_name='Postgres',
            sqlalchemy_uri='postgresql+psycopg2://superset:superset@postgres:5432/superset',
            expose_in_sqllab=True,
            allow_csv_upload=True,
            allow_run_async=False,
            allow_ctas=False,
            allow_cvas=False,
        )
        db.session.add(new_db)
        db.session.commit()
        db_id = new_db.id
        print(f"✅ PostgreSQL database created (ID: {db_id})")
    
    # 2. Sync schema (om tabellen te detecteren)
    print(f"\n🔍 Syncing database schema...")
    target_db = db.session.query(Database).get(db_id)
    
    # Import models
    from superset.connectors.sqla.models import SqlaTable
    
    # Check of dataset al bestaat
    existing_dataset = db.session.query(SqlaTable).filter(
        SqlaTable.database_id == db_id,
        SqlaTable.schema == 'cell_towers',
        SqlaTable.table_name == 'clean_204'
    ).first()
    
    if existing_dataset:
        print(f"✅ Dataset cell_towers.clean_204 already exists (ID: {existing_dataset.id})")
    else:
        print("📝 Creating cell_towers.clean_204 dataset...")
        
        # Get admin user
        admin = security_manager.find_user(username='admin')
        
        dataset = SqlaTable(
            table_name='clean_204',
            schema='cell_towers',
            database_id=db_id,
            owners=[admin] if admin else []
        )
        db.session.add(dataset)
        db.session.commit()
        print(f"✅ Dataset created (ID: {dataset.id})")
        
        # Sync columns
        dataset.fetch_metadata()
        db.session.commit()
        print(f"✅ Columns synced ({len(dataset.columns)} columns detected)")
    
    print("\n" + "="*60)
    print("🎉 SUCCESS!")
    print("="*60)
    print(f"\n✅ PostgreSQL database: ID {db_id}")
    print(f"✅ Dataset: cell_towers.clean_204")
    print(f"\n🌐 Open Superset: http://localhost:8088")
    print("📊 Go to: Data → Datasets")
    print("🎨 Find 'clean_204' and click 'Create Chart'")
    print("\n💡 Example query in SQL Lab:")
    print("   Database: Postgres")
    print("   Schema: cell_towers")
    print("   SELECT radio, COUNT(*) FROM clean_204 GROUP BY radio;")
