#!/usr/bin/env python3

import requests
import json
from datetime import datetime

# Supabase credentials from the provided information
SUPABASE_URL = "https://nucqowewuqeveocmsdnq.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51Y3Fvd2V3dXFldmVvY21zZG5xIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzI4MzIzNSwiZXhwIjoyMDc4ODU5MjM1fQ.2u1FZbp9G2U8T_P351613K1bcEQNxB8Y6GZA4ucaSqI"

def get_table_info(table_name):
    """Get basic info about a table"""
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Get first record to see structure
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}",
            headers=headers,
            params={"select": "*", "limit": 1}
        )

        if response.status_code == 200:
            data = response.json()
            if data:
                return {
                    "exists": True,
                    "sample_data": data[0],
                    "column_count": len(data[0]) if data else 0
                }
            else:
                return {
                    "exists": True,
                    "sample_data": None,
                    "column_count": 0,
                    "empty": True
                }
        elif response.status_code == 404:
            return {"exists": False}
        else:
            return {"exists": False, "error": f"Status {response.status_code}"}

    except Exception as e:
        return {"exists": False, "error": str(e)}

def get_table_record_count(table_name):
    """Get approximate record count for a table"""
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Count records (PostgREST doesn't support COUNT directly, so we use a workaround)
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}",
            headers=headers,
            params={"select": "id", "limit": 1000}  # Max limit to estimate
        )

        if response.status_code == 200:
            data = response.json()
            return len(data)
        else:
            return "Unknown"

    except Exception as e:
        return "Error"

def test_basic_connection():
    """Test basic connection to Supabase"""
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/operators",
            headers=headers,
            params={"select": "id", "limit": 1}
        )

        return response.status_code == 200

    except Exception as e:
        return False

def main():
    print("=" * 80)
    print("SUPABASE DATABASE REPORT")
    print("=" * 80)
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project URL: {SUPABASE_URL}")
    print(f"Project ID: nucqowewuqeveocmsdnq")
    print("=" * 80)

    # Test connection
    if not test_basic_connection():
        print("❌ Cannot connect to Supabase database")
        return

    print("✅ Successfully connected to Supabase database")
    print()

    # Known tables from the code analysis
    known_tables = ['operators', 'equipment', 'equipment_types']

    print("DATABASE TABLES ANALYSIS")
    print("-" * 80)

    all_tables_info = []

    for table_name in known_tables:
        print(f"\n📋 Table: {table_name}")
        print("-" * 40)

        table_info = get_table_info(table_name)

        if table_info["exists"]:
            print(f"✅ Status: EXISTS")

            if "sample_data" in table_info and table_info["sample_data"]:
                sample = table_info["sample_data"]
                columns = list(sample.keys())
                print(f"📊 Columns: {len(columns)}")
                print(f"📝 Sample columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")

                # Get record count
                count = get_table_record_count(table_name)
                print(f"🔢 Approximate records: {count}")

                # Show sample data (first few fields)
                print(f"📄 Sample data: {json.dumps(sample, indent=2, default=str)[:200]}...")
            elif table_info.get("empty"):
                print(f"✅ Status: EXISTS (but empty)")
            else:
                print(f"⚠️  Status: EXISTS (could not retrieve sample data)")

            all_tables_info.append({
                "table_name": table_name,
                "exists": True,
                "columns": table_info.get("column_count", 0),
                "records": get_table_record_count(table_name)
            })
        else:
            print(f"❌ Status: DOES NOT EXIST")
            error = table_info.get("error", "Unknown error")
            print(f"💥 Error: {error}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    existing_tables = [t for t in all_tables_info if t["exists"]]
    print(f"📊 Total tables found: {len(existing_tables)}/{len(known_tables)}")

    for table in existing_tables:
        print(f"  • {table['table_name']}: {table['records']} records, {table['columns']} columns")

    print("\n" + "=" * 80)
    print("CONNECTION DETAILS")
    print("=" * 80)
    print(f"🔑 Authentication: Service Role Key (full access)")
    print(f"🌐 API Endpoint: {SUPABASE_URL}/rest/v1/")
    print(f"📡 Connection Status: ✅ ACTIVE")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()