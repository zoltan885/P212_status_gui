import time
import json
import msgpack
import random
from sensor_pb2 import SensorData

# Simulate 300 sensors
NUM_SENSORS = 300
FREQ = 2  # messages per second per sensor
ITERATIONS = 1  # just one iteration to test size + speed

# Generate fake sensor data
def generate_sensor(i):
    return {
        "timestamp": int(time.time()),
        "sensor_name": f"temp_{i:03d}",
        "sensor_address": f"0x{i:02X}",
        "status": "ok",
        "value": round(random.uniform(20, 30), 2),
        "extra": {"battery": str(random.randint(80, 100))}
    }

# Benchmark JSON
json_start = time.time()
json_sizes = []
for _ in range(ITERATIONS):
    for i in range(NUM_SENSORS):
        data = generate_sensor(i)
        msg = json.dumps(data).encode()
        json_sizes.append(len(msg))
json_end = time.time()

# Benchmark MessagePack
mp_start = time.time()
mp_sizes = []
for _ in range(ITERATIONS):
    for i in range(NUM_SENSORS):
        data = generate_sensor(i)
        msg = msgpack.packb(data)
        mp_sizes.append(len(msg))
mp_end = time.time()

# Benchmark Protobuf
pb_start = time.time()
pb_sizes = []
for _ in range(ITERATIONS):
    for i in range(NUM_SENSORS):
        s = generate_sensor(i)
        data = SensorData(
            timestamp=s["timestamp"],
            sensor_name=s["sensor_name"],
            sensor_address=s["sensor_address"],
            status=s["status"],
            value=s["value"],
            extra=s["extra"]
        )
        msg = data.SerializeToString()
        pb_sizes.append(len(msg))
pb_end = time.time()

# Print results
def summarize(name, sizes, elapsed):
    print(f"{name}:")
    print(f"  Avg size: {sum(sizes)/len(sizes):.1f} bytes")
    print(f"  Total serialization time: {elapsed:.4f} s")
    print(f"  Throughput: {len(sizes)/elapsed:.1f} msgs/s\n")

summarize("JSON", json_sizes, json_end - json_start)
summarize("MessagePack", mp_sizes, mp_end - mp_start)
summarize("Protobuf", pb_sizes, pb_end - pb_start)
