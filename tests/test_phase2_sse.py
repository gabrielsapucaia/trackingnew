import requests
import threading
import time
import json
import sseclient

SSE_URL = "http://localhost:8080/api/events/stream"

def test_sse_headers():
    print("\n[TEST] SSE Headers")
    with requests.get(SSE_URL, stream=True) as r:
        ct = r.headers.get('Content-Type')
        cc = r.headers.get('Cache-Control')
        print(f"Content-Type: {ct}")
        print(f"Cache-Control: {cc}")
        assert "text/event-stream" in ct
        assert "no-store" in cc
    print("✅ Headers Test Passed")

def test_heartbeat():
    print("\n[TEST] SSE Heartbeat (Wait 20s)")
    start_time = time.time()
    heartbeats = 0
    
    try:
        response = requests.get(SSE_URL, stream=True, timeout=30)
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            if time.time() - start_time > 20:
                break
            if event.event == 'heartbeat':
                heartbeats += 1
                print(f"Heartbeat received at {time.time() - start_time:.1f}s")
    except Exception as e:
        print(f"Error: {e}")
    
    print(f"Total Heartbeats: {heartbeats}")
    assert heartbeats >= 1
    print("✅ Heartbeat Test Passed")

if __name__ == "__main__":
    try:
        test_sse_headers()
        test_heartbeat()
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        exit(1)
