#!/usr/bin/env python3
"""
End-to-End Keycloak + JWT RLS Demo
===================================

This script demonstrates the complete flow:
1. Authenticate with Keycloak (get JWT token)
2. Connect to PostgreSQL
3. Set JWT token in session
4. Execute queries with automatic RLS based on JWT roles
5. Show different results for different users
"""

import sys
import json
import requests
import psycopg2
from psycopg2 import sql
from typing import Optional, Dict, Any
import base64

# Configuration
KEYCLOAK_URL = "http://localhost:8085"
REALM = "data-platform"
CLIENT_ID = "data-platform-api"
CLIENT_SECRET = "api_client_secret_2025"

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "superset",
    "user": "superset",
    "password": "superset"
}

# Colors for output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_header(text: str):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text: str):
    print(f"{GREEN}✓ {text}{RESET}")

def print_info(text: str):
    print(f"{BLUE}ℹ {text}{RESET}")

def print_warning(text: str):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_error(text: str):
    print(f"{RED}✗ {text}{RESET}")

def get_keycloak_token(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Get OAuth token from Keycloak"""
    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "password",
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print_error(f"Failed to get token: {e}")
        return None

def decode_jwt_payload(token: str) -> Dict[str, Any]:
    """Decode JWT payload (for display purposes)"""
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        
        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = '=' * (4 - len(payload) % 4) if len(payload) % 4 else ''
        decoded = base64.b64decode(payload + padding)
        return json.loads(decoded)
    except Exception as e:
        print_error(f"Failed to decode JWT: {e}")
        return {}

def execute_with_jwt(username: str, password: str, display_name: str):
    """Execute queries with JWT token for a specific user"""
    print_header(f"Testing as: {display_name} ({username})")
    
    # Step 1: Get token from Keycloak
    print_info("Step 1: Getting OAuth token from Keycloak...")
    token_data = get_keycloak_token(username, password)
    
    if not token_data or 'access_token' not in token_data:
        print_error("Failed to get access token")
        return
    
    access_token = token_data['access_token']
    print_success(f"Token received (expires in {token_data.get('expires_in', '?')} seconds)")
    
    # Decode and show JWT claims
    payload = decode_jwt_payload(access_token)
    if payload:
        print_info(f"Username: {payload.get('preferred_username', 'N/A')}")
        print_info(f"Email: {payload.get('email', 'N/A')}")
        roles = payload.get('realm_access', {}).get('roles', [])
        custom_roles = [r for r in roles if r not in ['offline_access', 'default-roles-data-platform', 'uma_authorization']]
        print_info(f"Roles: {', '.join(custom_roles) if custom_roles else 'None'}")
    
    # Step 2: Connect to PostgreSQL
    print_info("\nStep 2: Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cur = conn.cursor()
        print_success("Connected to PostgreSQL")
        
        # Step 3: Set JWT token in session
        print_info("\nStep 3: Setting JWT token in PostgreSQL session...")
        cur.execute("SET app.jwt_token = %s;", (access_token,))
        print_success("JWT token set")
        
        # Step 4: Test JWT functions
        print_info("\nStep 4: Testing JWT functions...")
        cur.execute("""
            SELECT 
                get_jwt_username() as username,
                get_jwt_email() as email,
                get_jwt_roles() as roles,
                has_role('platform_admin') as is_admin,
                has_role('data_engineer') as is_engineer,
                has_role('data_analyst') as is_analyst,
                has_role('investigator') as is_investigator
        """)
        result = cur.fetchone()
        print(f"  Username: {result[0]}")
        print(f"  Email: {result[1]}")
        print(f"  Roles: {result[2]}")
        print(f"  Is Admin: {result[3]}")
        print(f"  Is Engineer: {result[4]}")
        print(f"  Is Analyst: {result[5]}")
        print(f"  Is Investigator: {result[6]}")
        
        # Step 5: Query data (RLS will filter based on JWT)
        print_info("\nStep 5: Querying investigations (RLS applied via JWT)...")
        cur.execute("""
            SELECT investigation_id, status, created_at 
            FROM investigations 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        investigations = cur.fetchall()
        
        if investigations:
            print_success(f"Found {len(investigations)} investigations:")
            for inv in investigations:
                print(f"  - {inv[0]}: {inv[1]} (created: {inv[2]})")
        else:
            print_warning("No investigations visible (RLS filtered all rows)")
        
        # Step 6: Query transactions
        print_info("\nStep 6: Querying transactions (RLS applied)...")
        cur.execute("""
            SELECT COUNT(*) as total
            FROM raw_transactions
        """)
        tx_count = cur.fetchone()[0]
        print(f"  Visible transactions: {tx_count}")
        
        # Cleanup
        cur.close()
        conn.close()
        print_success("\nSession completed")
        
    except psycopg2.Error as e:
        print_error(f"Database error: {e}")
    except Exception as e:
        print_error(f"Error: {e}")

def main():
    """Main demo flow"""
    print_header("Keycloak + JWT RLS End-to-End Demo")
    
    # Test users with different roles
    users = [
        ("admin.user", "Admin2025!", "Platform Admin"),
        ("john.engineer", "Engineer2025!", "Data Engineer"),
        ("bob.analyst", "Analyst2025!", "Data Analyst"),
        ("jane.investigator", "Investigator2025!", "Investigator"),
    ]
    
    for username, password, display_name in users:
        execute_with_jwt(username, password, display_name)
        print("\n" + "-" * 60)
    
    print_header("Demo Completed!")
    print_info("Key Takeaways:")
    print("  1. Each user gets a JWT token from Keycloak")
    print("  2. JWT token is set in PostgreSQL session (app.jwt_token)")
    print("  3. RLS policies automatically use JWT claims")
    print("  4. Different users see different data based on their roles")
    print("  5. No need to create database users - all auth via Keycloak")
    print()

if __name__ == "__main__":
    # Check if psycopg2 is installed
    try:
        import psycopg2
        import requests
    except ImportError:
        print_error("Required packages not installed!")
        print_info("Install with: pip install psycopg2-binary requests")
        sys.exit(1)
    
    main()
