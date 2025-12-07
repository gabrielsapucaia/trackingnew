import time
import threading
import uuid
from test_phase1_backend import publish_telemetry

def load_test():
    print("\n[TEST] Load Test: 1000 msg/s for 10s")
    
    device_count = 100
    msgs_per_device = 100
    # Total 10,000 messages
    
    start_time = time.time()
    
    threads = []
    for i in range(device_count):
        device_id = f"load_test_{i}"
        t = threading.Thread(target=publish_telemetry, args=(device_id, msgs_per_device, 0.001))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    print(f"Total Duration: {duration:.2f}s")
    print(f"Throughput: {10000/duration:.2f} msg/s")
    
    print("✅ Load Test Completed")

if __name__ == "__main__":
    load_test()
