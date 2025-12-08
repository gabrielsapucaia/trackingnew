#!/usr/bin/env python3

import requests
import json

# Supabase credentials from the provided information
SUPABASE_URL = "https://nucqowewuqeveocmsdnq.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51Y3Fvd2V3dXFldmVvY21zZG5xIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzI4MzIzNSwiZXhwIjoyMDc4ODU5MjM1fQ.2u1FZbp9G2U8T_P351613K1bcEQNxB8Y6GZA4ucaSqI"

def get_supabase_tables():
    """
    Connect to Supabase and retrieve all tables in the database
    """
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Query the information_schema.tables to get all public tables
        # Using the correct Supabase REST API format
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/",
            headers=headers,
            params={
                "select": "table_name",
                "from": "information_schema.tables",
                "table_schema": "eq.public",
                "table_type": "eq.BASE TABLE",
                "order": "table_name.asc"
            }
        )

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                tables = [item.get('table_name') for item in data if 'table_name' in item]
                return tables
            else:
                print(f"Unexpected response format: {data}")
                return None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return None

def get_tables_alternative():
    """
    Alternative approach: try to list tables by attempting to access common table names
    """
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Try to access some common tables that we know exist from the code
        common_tables = ['operators', 'equipment', 'equipment_types']

        found_tables = []

        for table in common_tables:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                params={"select": "id", "limit": 1}
            )

            if response.status_code == 200:
                found_tables.append(table)
                print(f"  ✓ Found table: {table}")
            elif response.status_code == 404:
                print(f"  ✗ Table not found: {table}")
            else:
                print(f"  ? Error accessing {table}: {response.status_code}")

        return found_tables

    except Exception as e:
        print(f"Error in alternative approach: {e}")
        return []

def test_basic_connection():
    """Test basic connection to Supabase"""
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Try to access a known table (operators) to test connection
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/operators",
            headers=headers,
            params={"select": "id,name", "limit": 1}
        )

        if response.status_code == 200:
            print("✓ Basic connection successful")
            return True
        else:
            print(f"✗ Basic connection failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def main():
    print("Supabase Table Checker")
    print("=" * 40)
    print(f"Project URL: {SUPABASE_URL}")
    print(f"Project ID: nucqowewuqeveocmsdnq")
    print("=" * 40)

    # Test basic connection first
    if not test_basic_connection():
        print("Cannot proceed without valid connection")
        return

    print("\nAttempting to fetch tables from Supabase database...")
    tables = get_supabase_tables()

    if tables:
        print(f"\n✓ Found {len(tables)} tables in Supabase database:")
        print("-" * 50)
        for i, table in enumerate(tables, 1):
            print(f"{i:2d}. {table}")
        print("-" * 50)
    else:
        print("\n✗ Failed to retrieve tables using direct query")
        print("\nTrying alternative approach to discover tables...")

        found_tables = get_tables_alternative()

        if found_tables:
            print(f"\n✓ Found {len(found_tables)} tables using alternative method:")
            print("-" * 50)
            for i, table in enumerate(found_tables, 1):
                print(f"{i:2d}. {table}")
            print("-" * 50)
        else:
            print("\n✗ Could not discover any tables")

if __name__ == "__main__":
    main()