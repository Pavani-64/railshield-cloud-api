def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_duplicate_node_name_is_rejected(client):
    client.post("/nodes", json={"name": "node-1", "location": "KM 12"})
    r = client.post("/nodes", json={"name": "node-1", "location": "KM 99"})
    assert r.status_code == 409


def test_sensor_thresholds_must_be_ordered(client):
    node = client.post("/nodes", json={"name": "node-1", "location": "KM 12"}).json()
    r = client.post(
        f"/nodes/{node['id']}/sensors",
        json={"name": "t", "sensor_type": "temperature", "unit": "C",
              "min_threshold": 50, "max_threshold": 10},
    )
    assert r.status_code == 422


def test_normal_reading_raises_no_alert(client, sensor):
    r = client.post("/readings", json={"sensor_id": sensor["id"], "value": 25.0})
    assert r.status_code == 201
    assert r.json()["alert"] is None


def test_out_of_range_reading_raises_alert(client, sensor):
    r = client.post("/readings", json={"sensor_id": sensor["id"], "value": 75.5})
    alert = r.json()["alert"]
    assert alert is not None
    assert "above maximum" in alert["message"]
    assert client.get("/alerts", params={"acknowledged": False}).json()[0]["id"] == alert["id"]


def test_reading_for_unknown_sensor_returns_404(client):
    r = client.post("/readings", json={"sensor_id": 999, "value": 1.0})
    assert r.status_code == 404


def test_batch_is_all_or_nothing(client, sensor):
    r = client.post(
        "/readings/batch",
        json=[{"sensor_id": sensor["id"], "value": 10}, {"sensor_id": 999, "value": 10}],
    )
    assert r.status_code == 404
    history = client.get(f"/sensors/{sensor['id']}/readings").json()
    assert history == []  # the valid first reading was rolled back too


def test_batch_counts_alerts(client, sensor):
    r = client.post(
        "/readings/batch",
        json=[{"sensor_id": sensor["id"], "value": v} for v in (10, -5, 70, 30)],
    )
    assert r.json() == {"readings_saved": 4, "alerts_raised": 2}


def test_latest_reading_per_sensor(client, sensor):
    node_id = sensor["node_id"]
    other = client.post(
        f"/nodes/{node_id}/sensors",
        json={"name": "vib", "sensor_type": "vibration", "unit": "g"},
    ).json()
    for value, ts in [(20, "2026-01-01T10:00:00Z"), (22, "2026-01-01T10:05:00Z"),
                      (21, "2026-01-01T10:01:00Z")]:
        client.post("/readings", json={"sensor_id": sensor["id"], "value": value, "recorded_at": ts})
    client.post("/readings", json={"sensor_id": other["id"], "value": 0.3,
                                   "recorded_at": "2026-01-01T09:00:00Z"})

    latest = client.get(f"/nodes/{node_id}/latest").json()
    assert {(x["sensor_name"], x["value"]) for x in latest} == {("temp", 22), ("vib", 0.3)}


def test_history_time_range_filter(client, sensor):
    for hour in (8, 9, 10, 11):
        client.post("/readings", json={"sensor_id": sensor["id"], "value": hour,
                                       "recorded_at": f"2026-01-01T{hour:02d}:00:00Z"})
    r = client.get(
        f"/sensors/{sensor['id']}/readings",
        params={"start": "2026-01-01T09:00:00Z", "end": "2026-01-01T10:00:00Z"},
    )
    assert [x["value"] for x in r.json()] == [10, 9]


def test_acknowledge_alert(client, sensor):
    alert = client.post("/readings", json={"sensor_id": sensor["id"], "value": 99}).json()["alert"]
    r = client.patch(f"/alerts/{alert['id']}/acknowledge")
    assert r.json()["acknowledged"] is True
    assert client.get("/alerts", params={"acknowledged": False}).json() == []
