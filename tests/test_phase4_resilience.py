import time
import requests
import subprocess
import psycopg2
from test_phase1_backend import publish_telemetry, get_db_connection

API_URL = "http://localhost:8080"

def get_offline_queue_size():
    try:
        r = requests.get(f"{API_URL}/stats")
        return r.json().get("offline_queue_size", 0)
    except:
        return -1

def test_db_outage():
    print("\n[TEST] Resilience: DB Outage -> Offline Queue")
    
    try:
        # 1. Stop DB
        print("Stopping TimescaleDB...")
        subprocess.run(["docker", "stop", "aura_timescaledb"], check=True)
        time.sleep(5)
        
        # 2. Publish Data
        print("Publishing 5 messages during outage...")
        device_id = "test_resilience_001"
        publish_telemetry(device_id, count=5, interval=0.1)
        
        # Wait for batch timeout (5s) + connect timeout (10s) + buffer
        print("Waiting 20s for batch flush & failure detection...")
        time.sleep(20)
        
        # Trigger flush by sending one more message (since flush is event-driven)
        print("Sending trigger message to force flush...")
        publish_telemetry("trigger_flush", count=1)
        time.sleep(5) # Wait for processing
        
        # 3. Check Queue Size
        q_size = get_offline_queue_size()
        print(f"Offline Queue Size: {q_size}")
        assert q_size >= 5, f"Expected queue >= 5, got {q_size}"
        
    finally:
        # 4. Restart DB (Always)
        print("Restarting TimescaleDB...")
        subprocess.run(["docker", "start", "aura_timescaledb"], check=True)
    
    # Wait for DB to be ready
    print("Waiting for DB recovery (20s)...")
    time.sleep(20)
    
    # 5. Check Queue Drain
    q_size_after = get_offline_queue_size()
    print(f"Offline Queue Size after recovery: {q_size_after}")
    assert q_size_after == 0, f"Expected queue 0, got {q_size_after}"
    
    # 6. Verify Data in DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM telemetry WHERE device_id = %s", (device_id,))
    count = cur.fetchone()[0]
    conn.close()
    print(f"DB Count for {device_id}: {count}")
    assert count == 5, f"Expected 5 records, found {count}"
    
    print("✅ Resilience Test Passed")

if __name__ == "__main__":
    try:
        test_db_outage()
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        exit(1)
