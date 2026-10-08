# RailShield Cloud API

Backend for **RailShield**, my IoT railway safety and monitoring system. The ESP32 field nodes measure track conditions. This API stores their readings in PostgreSQL, checks each reading against safe limits, and raises alerts that an operator can review and acknowledge.

Built with **Python, FastAPI, SQLAlchemy and PostgreSQL**.

## Architecture

```
ESP32 sensor nodes ──LoRa──> The Things Network ──HTTP──> RailShield Cloud API ──> PostgreSQL
                                                              │
                                     dashboards / operators <─┘  (REST: latest values, history, alerts)
```

The API is split into layers:

| Layer | File | Job |
|---|---|---|
| HTTP routes | `app/routers/*.py` | Validate requests, return the right status codes |
| Business logic | `app/services.py` | Threshold checks, ingesting readings, the "latest reading" query |
| Data model | `app/models.py` | Table definitions (SQLAlchemy ORM) |
| Schemas | `app/schemas.py` | Request/response shapes (Pydantic) |
| Database | `app/database.py` | Connection and session per request |

## Database schema

```
nodes      (id, name UNIQUE, location, created_at)
sensors    (id, node_id → nodes, name, sensor_type, unit, min_threshold, max_threshold)
             UNIQUE (node_id, name)
readings   (id, sensor_id → sensors, value, recorded_at)
             INDEX (sensor_id, recorded_at)
alerts     (id, sensor_id → sensors, reading_id → readings UNIQUE, message, created_at, acknowledged)
```

## API endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/nodes` | Register a node |
| GET | `/nodes` | List nodes |
| POST | `/nodes/{id}/sensors` | Add a sensor (with optional min/max thresholds) to a node |
| GET | `/nodes/{id}/sensors` | List a node's sensors |
| GET | `/nodes/{id}/latest` | Latest value of every sensor on a node |
| POST | `/readings` | Send one reading; returns the alert if one was raised |
| POST | `/readings/batch` | Send up to 1000 readings in one all-or-nothing transaction |
| GET | `/sensors/{id}/readings?start=&end=&limit=` | Reading history for a time range |
| GET | `/alerts?acknowledged=false&node_id=` | List alerts |
| PATCH | `/alerts/{id}/acknowledge` | Mark an alert as handled |
| GET | `/health` | Health check |

Interactive docs are generated automatically at `http://127.0.0.1:8000/docs`.

## Design decisions

- **Batch upload is all-or-nothing.** A node that was offline uploads its stored readings in one request. If any reading is invalid, the whole batch is rolled back, so the database never holds half a batch.
- **Composite index on `(sensor_id, recorded_at)`.** `readings` is the table that grows fastest, and the most common query is "readings for one sensor in a time range". The index serves exactly that query.
- **Latest reading per sensor in one query.** Uses a SQL window function (`ROW_NUMBER() OVER (PARTITION BY sensor_id ...)`) instead of one query per sensor.
- **Business logic separate from routes.** `services.ingest_reading` doesn't commit, so the same function serves both the single and the batch endpoint, and the route decides the transaction boundary.
- **Database constraints, not just code checks.** Unique node names and unique sensor names per node are enforced by the database. The API turns violations into `409 Conflict`.

## Running it locally (Windows)

1. Install PostgreSQL from https://www.postgresql.org/download/windows/ and remember the password you set for the `postgres` user.
2. Create the databases (in **SQL Shell (psql)** from the Start menu):
   ```sql
   CREATE DATABASE railshield;
   CREATE DATABASE railshield_test;
   ```
3. Set up the project:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
   Then edit `.env` and put in your PostgreSQL password.
4. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```
   Open http://127.0.0.1:8000/docs.
5. In a second terminal, simulate three RailShield nodes sending data:
   ```bash
   python scripts/simulate_nodes.py --rounds 20 --interval 1
   ```

Without a `.env` file the app falls back to a local SQLite file, which is handy for a quick try but isn't the intended setup.

## Tests

```powershell
pytest                       # fast, uses in-memory SQLite

# Same tests against real PostgreSQL (PowerShell):
$env:TEST_DATABASE_URL="postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/railshield_test"
pytest
```

The tests cover alert creation, the all-or-nothing batch rollback, the latest-reading query, time-range filtering, duplicate and validation errors, and acknowledging alerts.

## Possible next steps

- Alembic migrations instead of `create_all`
- API-key authentication for nodes
- Docker Compose setup
- Pagination by cursor for very large histories
