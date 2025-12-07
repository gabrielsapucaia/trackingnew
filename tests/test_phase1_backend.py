import time
import json
import uuid
import threading
import requests
import paho.mqtt.client as mqtt
import psycopg2
from datetime import datetime

# Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "aura/tracking"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "auratracking"
DB_USER = "aura"
DB_PASS = "aura2025"

SSE_URL = "http://localhost:8080/api/events/stream"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def publish_telemetry(device_id, count=1, interval=1.0):
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    for i in range(count):
        payload = {
            "deviceId": device_id,
            "timestamp": int(time.time() * 1000),
            "gps": {
                "lat": -23.5505 + (i * 0.0001),
                "lon": -46.6333 + (i * 0.0001),
                "speed": 10.0 + i,
                "bearing": 0.0,
                "accuracy": 5.0,
                "altitude": 800.0
            },
            "status": "active"
        }
        client.publish(f"{MQTT_TOPIC_PREFIX}/{device_id}", json.dumps(payload))
        if interval > 0:
            time.sleep(interval)
    
    client.disconnect()

def test_ingestion():
    print("\n[TEST] Ingestion: MQTT -> DB")
    device_id = f"test_ingest_{uuid.uuid4().hex[:8]}"
    
    # Publish 1 message
    publish_telemetry(device_id, count=1)
    print(f"Published 1 message for {device_id}")
    
    # Wait for ingestion (batch timeout is 300ms, give it 2s)
    time.sleep(2)
    
    # Check DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM telemetry WHERE device_id = %s", (device_id,))
    count = cur.fetchone()[0]
    conn.close()
    
    print(f"DB Count for {device_id}: {count}")
    assert count == 1, f"Expected 1 record, found {count}"
    print("✅ Ingestion Test Passed")

def test_throttle():
    print("\n[TEST] Throttle: 10Hz Publish -> SSE Limit")
    device_id = f"test_throttle_{uuid.uuid4().hex[:8]}"
    
    # Listener for SSE
    events_received = []
    stop_event = threading.Event()
    
    def sse_listener():
        print("SSE Listener started...")
        current_event = None
        try:
            response = requests.get(SSE_URL, stream=True, timeout=10)
            print(f"SSE Connected. Status: {response.status_code}")
            for line in response.iter_lines():
                if stop_event.is_set():
                    break
                if line:
                    decoded_line = line.decode('utf-8')
                    # print(f"SSE RAW: {decoded_line}") # Debug
                    if decoded_line.startswith("event:"):
                        current_event = decoded_line[6:].strip()
                    elif decoded_line.startswith("data:"):
                        try:
                            # Handle simple data (heartbeat) or json
                            payload_str = decoded_line[5:].strip()
                            if current_event == 'heartbeat':
                                # print("Heartbeat received")
                                pass
                            elif current_event == 'device-update':
                                data = json.loads(payload_str)
                                if data.get('id') == device_id:
                                    print(f"Event received for {device_id}")
                                    events_received.append(data)
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"SSE Error: {e}")

    t = threading.Thread(target=sse_listener)
    t.start()
    
    # Give time to connect
    print("Waiting 3s for SSE connection...")
    time.sleep(3)
    
    # Publish 10 messages in 1 second (10Hz)
    print(f"Publishing 10 messages for {device_id} at 10Hz...")
    publish_telemetry(device_id, count=10, interval=0.1)
    
    # Wait for throttle window (5s) + buffer
    print("Waiting 6 seconds...")
    time.sleep(6)
    stop_event.set()
    # Force close connection if needed or just wait for join
    t.join(timeout=2)
    
    print(f"SSE Events Received: {len(events_received)}")
    
    # Check DB persistence (should be 100%)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM telemetry WHERE device_id = %s", (device_id,))
    db_count = cur.fetchone()[0]
    conn.close()
    
    print(f"DB Count: {db_count}")
    
    # Assertions
    assert db_count == 10, f"Expected 10 DB records, found {db_count}"
    # Throttle is 5s. We sent for 1s. We waited 6s.
    # We expect at least 1 event (immediate).
    # Maybe a second one if the window reset?
    # Strict throttle: <= 1 event / 5s.
    assert 1 <= len(events_received) <= 3, f"Expected 1-3 events, received {len(events_received)}"
    
    print("✅ Throttle Test Passed")

if __name__ == "__main__":
    try:
        test_ingestion()
        test_throttle()
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        exit(1)
