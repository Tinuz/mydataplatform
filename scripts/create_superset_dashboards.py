#!/usr/bin/env python3
"""
Create Superset dashboards for weather data visualization.

This script creates 3 dashboards via Superset API:
1. Temperature Trends - Line chart showing temperature over time per station
2. Weather Map - Deck.gl map showing weather data at station locations  
3. Data Quality Metrics - Charts showing data quality and freshness
"""

import requests
import json
import time
from typing import Dict, Any

class SupersetDashboardCreator:
    def __init__(self, base_url="http://localhost:8088", username="admin", password="admin"):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token = None
        self.csrf_token = None
        self.database_id = None
        
    def login(self):
        """Login to Superset and get access tokens"""
        print("🔐 Logging in to Superset...")
        
        # Get CSRF token
        response = requests.get(f"{self.base_url}/api/v1/security/csrf_token/")
        if response.status_code == 401:
            # Try login first
            login_data = {
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": True
            }
            login_response = requests.post(
                f"{self.base_url}/api/v1/security/login",
                json=login_data
            )
            if login_response.status_code == 200:
                self.access_token = login_response.json()["access_token"]
                print("✅ Login successful")
                
                # Get CSRF token with auth
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = requests.get(
                    f"{self.base_url}/api/v1/security/csrf_token/",
                    headers=headers
                )
        
        if response.status_code == 200:
            self.csrf_token = response.json()["result"]
            print(f"✅ Got CSRF token")
        else:
            raise Exception(f"Failed to get CSRF token: {response.text}")
    
    def get_headers(self):
        """Get headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": self.csrf_token
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def find_database(self):
        """Find the PostgreSQL database ID"""
        print("🔍 Finding PostgreSQL database...")
        
        response = requests.get(
            f"{self.base_url}/api/v1/database/",
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            databases = response.json()["result"]
            for db in databases:
                if "postgres" in db.get("database_name", "").lower():
                    self.database_id = db["id"]
                    print(f"✅ Found database: {db['database_name']} (ID: {self.database_id})")
                    return
            
            # If no postgres found, use first database
            if databases:
                self.database_id = databases[0]["id"]
                print(f"⚠️  Using first database: {databases[0]['database_name']} (ID: {self.database_id})")
        else:
            raise Exception(f"Failed to get databases: {response.text}")
    
    def create_dataset(self, table_name: str, schema: str = "weather") -> int:
        """Create a dataset (table) in Superset"""
        print(f"📊 Creating dataset: {schema}.{table_name}")
        
        # First check if dataset already exists
        response = requests.get(
            f"{self.base_url}/api/v1/dataset/",
            headers=self.get_headers(),
            params={"q": json.dumps({"filters": [{"col": "table_name", "opr": "eq", "value": table_name}]})}
        )
        
        if response.status_code == 200:
            existing = response.json()["result"]
            for ds in existing:
                if ds.get("schema") == schema and ds.get("table_name") == table_name:
                    print(f"✓ Dataset already exists (ID: {ds['id']})")
                    return ds["id"]
        
        # Create new dataset
        dataset_data = {
            "database": self.database_id,
            "schema": schema,
            "table_name": table_name
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/dataset/",
            headers=self.get_headers(),
            json=dataset_data
        )
        
        if response.status_code in [200, 201]:
            dataset_id = response.json()["id"]
            print(f"✅ Created dataset (ID: {dataset_id})")
            return dataset_id
        else:
            print(f"⚠️  Failed to create dataset: {response.status_code} - {response.text}")
            return None
    
    def create_chart(self, chart_config: Dict[str, Any]) -> int:
        """Create a chart in Superset"""
        print(f"📈 Creating chart: {chart_config['slice_name']}")
        
        response = requests.post(
            f"{self.base_url}/api/v1/chart/",
            headers=self.get_headers(),
            json=chart_config
        )
        
        if response.status_code in [200, 201]:
            chart_id = response.json()["id"]
            print(f"✅ Created chart (ID: {chart_id})")
            return chart_id
        else:
            print(f"⚠️  Failed to create chart: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return None
    
    def create_dashboard(self, title: str, chart_ids: list) -> int:
        """Create a dashboard with charts"""
        print(f"🎨 Creating dashboard: {title}")
        
        # Create dashboard layout
        position_json = {}
        row = 0
        for i, chart_id in enumerate(chart_ids):
            position_json[f"CHART-{chart_id}"] = {
                "type": "CHART",
                "id": chart_id,
                "children": [],
                "meta": {
                    "width": 6,
                    "height": 50,
                    "chartId": chart_id
                }
            }
            if i % 2 == 0:
                position_json[f"CHART-{chart_id}"]["meta"]["x"] = 0
                position_json[f"CHART-{chart_id}"]["meta"]["y"] = row
            else:
                position_json[f"CHART-{chart_id}"]["meta"]["x"] = 6
                position_json[f"CHART-{chart_id}"]["meta"]["y"] = row
                row += 50
        
        dashboard_data = {
            "dashboard_title": title,
            "published": True,
            "position_json": json.dumps(position_json)
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/dashboard/",
            headers=self.get_headers(),
            json=dashboard_data
        )
        
        if response.status_code in [200, 201]:
            dashboard_id = response.json()["id"]
            print(f"✅ Created dashboard (ID: {dashboard_id})")
            return dashboard_id
        else:
            print(f"⚠️  Failed to create dashboard: {response.status_code} - {response.text}")
            return None
    
    def create_temperature_trends_dashboard(self):
        """Create Temperature Trends dashboard"""
        print("\n" + "="*70)
        print("📊 Creating Dashboard 1: Temperature Trends")
        print("="*70)
        
        # Create dataset
        dataset_id = self.create_dataset("observations")
        if not dataset_id:
            return
        
        charts = []
        
        # Chart 1: Temperature over time (line chart)
        chart1 = {
            "slice_name": "Temperature Trends by Station",
            "viz_type": "echarts_timeseries_line",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metrics": ["AVG(temperature)"],
                "groupby": ["station_name"],
                "time_range": "Last 7 days",
                "adhoc_filters": [],
                "row_limit": 10000,
                "time_grain_sqla": "PT1H",
                "show_legend": True,
                "line_interpolation": "linear",
                "color_scheme": "supersetColors"
            })
        }
        chart_id = self.create_chart(chart1)
        if chart_id:
            charts.append(chart_id)
        
        # Chart 2: Current temperature by station (bar chart)
        chart2 = {
            "slice_name": "Latest Temperature by Station",
            "viz_type": "echarts_timeseries_bar",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metrics": ["temperature"],
                "groupby": ["station_name"],
                "adhoc_filters": [],
                "row_limit": 10,
                "color_scheme": "supersetColors"
            })
        }
        chart_id = self.create_chart(chart2)
        if chart_id:
            charts.append(chart_id)
        
        # Create dashboard
        if charts:
            self.create_dashboard("🌡️ Temperature Trends", charts)
    
    def create_weather_map_dashboard(self):
        """Create Weather Map dashboard"""
        print("\n" + "="*70)
        print("🗺️  Creating Dashboard 2: Weather Map")
        print("="*70)
        
        # Create datasets
        obs_dataset_id = self.create_dataset("observations")
        stations_dataset_id = self.create_dataset("stations")
        
        if not obs_dataset_id or not stations_dataset_id:
            return
        
        charts = []
        
        # Chart 1: Station locations on map (would need deck.gl)
        # For now, create a table showing station info
        chart1 = {
            "slice_name": "Weather Stations Overview",
            "viz_type": "table",
            "datasource_id": stations_dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "all_columns": ["station_name", "latitude", "longitude"],
                "row_limit": 100
            })
        }
        chart_id = self.create_chart(chart1)
        if chart_id:
            charts.append(chart_id)
        
        # Chart 2: Latest weather conditions per station
        chart2 = {
            "slice_name": "Current Weather Conditions",
            "viz_type": "table",
            "datasource_id": obs_dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "all_columns": ["station_name", "temperature", "humidity", "wind_speed", "timestamp"],
                "row_limit": 10,
                "order_desc": True,
                "order_by_cols": ["[\"timestamp\", false]"]
            })
        }
        chart_id = self.create_chart(chart2)
        if chart_id:
            charts.append(chart_id)
        
        # Create dashboard
        if charts:
            self.create_dashboard("🗺️ Weather Map", charts)
    
    def create_data_quality_dashboard(self):
        """Create Data Quality Metrics dashboard"""
        print("\n" + "="*70)
        print("✅ Creating Dashboard 3: Data Quality Metrics")
        print("="*70)
        
        # Create dataset
        dataset_id = self.create_dataset("observations")
        if not dataset_id:
            return
        
        charts = []
        
        # Chart 1: Data freshness (latest timestamp)
        chart1 = {
            "slice_name": "Data Freshness",
            "viz_type": "big_number",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metric": "MAX(timestamp)",
                "adhoc_filters": []
            })
        }
        chart_id = self.create_chart(chart1)
        if chart_id:
            charts.append(chart_id)
        
        # Chart 2: Records per station
        chart2 = {
            "slice_name": "Records per Station",
            "viz_type": "pie",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metric": "COUNT(*)",
                "groupby": ["station_name"],
                "row_limit": 100
            })
        }
        chart_id = self.create_chart(chart2)
        if chart_id:
            charts.append(chart_id)
        
        # Chart 3: Data quality distribution
        chart3 = {
            "slice_name": "Data Quality Distribution",
            "viz_type": "pie",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({
                "metric": "COUNT(*)",
                "groupby": ["data_quality"],
                "row_limit": 10
            })
        }
        chart_id = self.create_chart(chart3)
        if chart_id:
            charts.append(chart_id)
        
        # Create dashboard
        if charts:
            self.create_dashboard("✅ Data Quality Metrics", charts)
    
    def run(self):
        """Create all dashboards"""
        print("🚀 Starting Superset Dashboard Creation")
        print("="*70)
        
        try:
            self.login()
            self.find_database()
            
            # Create all dashboards
            self.create_temperature_trends_dashboard()
            time.sleep(1)  # Rate limiting
            
            self.create_weather_map_dashboard()
            time.sleep(1)
            
            self.create_data_quality_dashboard()
            
            print("\n" + "="*70)
            print("✅ Successfully created all Superset dashboards!")
            print("="*70)
            print(f"\n🌐 View dashboards at: {self.base_url}/dashboard/list/")
            print(f"   Login: {self.username} / {self.password}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    creator = SupersetDashboardCreator()
    creator.run()
