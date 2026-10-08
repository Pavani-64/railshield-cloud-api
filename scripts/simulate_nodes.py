"""Pretend to be RailShield field nodes and send readings to the API.

Usage (with the API running):
    python scripts/simulate_nodes.py --rounds 20 --interval 1
"""
import argparse
import random
import time

import httpx

# Change these to match the sensors on your real RailShield nodes.
NODES = [
    {"name": "node-km-12", "location": "Track section KM 12"},
    {"name": "node-km-18", "location": "Track section KM 18"},
    {"name": "node-km-25", "location": "Track section KM 25"},
]
SENSORS = [
    # name, type, unit, min, max, normal range for the simulation
    ("temp", "temperature", "C", 0, 60, (20, 45)),
    ("vibration", "vibration", "g", None, 2.0, (0.1, 1.2)),
    ("tilt", "tilt", "deg", -5, 5, (-1.5, 1.5)),
]


def setup(client: httpx.Client) -> list[dict]:
    """Create the nodes and sensors if they don't exist yet. Returns all sensors."""
    existing = {n["name"]: n for n in client.get("/nodes").json()}
    sensors = []
    for node_data in NODES:
        node = existing.get(node_data["name"]) or client.post("/nodes", json=node_data).json()
        current = {s["name"]: s for s in client.get(f"/nodes/{node['id']}/sensors").json()}
        for name, stype, unit, lo, hi, normal in SENSORS:
            sensor = current.get(name) or client.post(
                f"/nodes/{node['id']}/sensors",
                json={"name": name, "sensor_type": stype, "unit": unit,
                      "min_threshold": lo, "max_threshold": hi},
            ).json()
            sensor["normal"] = normal
            sensors.append(sensor)
    return sensors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between rounds")
    parser.add_argument("--fault-rate", type=float, default=0.05,
                        help="chance that a reading is out of range")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=10) as client:
        sensors = setup(client)
        print(f"Sending readings for {len(sensors)} sensors on {len(NODES)} nodes...")
        for i in range(args.rounds):
            batch = []
            for s in sensors:
                lo, hi = s["normal"]
                value = random.uniform(lo, hi)
                if random.random() < args.fault_rate:
                    value = hi * 3 + 1  # simulate a fault
                batch.append({"sensor_id": s["id"], "value": round(value, 2)})
            result = client.post("/readings/batch", json=batch).json()
            print(f"round {i + 1}: {result}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
