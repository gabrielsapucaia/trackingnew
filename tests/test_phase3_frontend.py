import requests
import time
import threading
import json

API_URL = "http://localhost:8080/api"

def test_frontend_bootstrap():
    print("\n[TEST] Frontend Bootstrap (GET /devices)")
    try:
        r = requests.get(f"{API_URL}/devices")
        assert r.status_code == 200
        data = r.json()
        devices = data.get('devices', [])
        print(f"Devices found: {len(devices)}")
        # Check structure
        if len(devices) > 0:
            d = devices[0]
            print(f"First device: {d}")
            assert "device_id" in d
            assert "latitude" in d
            assert "longitude" in d
        print("✅ Bootstrap Test Passed")
    except Exception as e:
        print(f"❌ Bootstrap Failed: {e}")
        raise

def test_frontend_flow():
    print("\n[TEST] Frontend Flow (Bootstrap -> SSE)")
    
    # 1. Bootstrap
    r = requests.get(f"{API_URL}/devices")
    initial_devices = {d['device_id']: d for d in r.json().get('devices', [])}
    print(f"Initial state: {len(initial_devices)} devices")
    
    # 2. SSE Connection
    print("Connecting to SSE...")
    stop_event = threading.Event()
    updates_received = 0
    
    def sse_client():
        nonlocal updates_received
        try:
            with requests.get(f"{API_URL}/events/stream", stream=True, timeout=30) as r:
                for line in r.iter_lines():
                    if stop_event.is_set():
                        break
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data:"):
                            updates_received += 1
        except Exception as e:
            print(f"SSE Error: {e}")

    t = threading.Thread(target=sse_client)
    t.start()
    
    time.sleep(5)
    print(f"Updates received in 5s: {updates_received}")
    
    stop_event.set()
    t.join(timeout=2)
    
    if updates_received > 0:
        print("✅ SSE Flow Test Passed")
    else:
        print("⚠️ No updates received (System might be idle)")

if __name__ == "__main__":
    try:
        test_frontend_bootstrap()
        test_frontend_flow()
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        exit(1)
