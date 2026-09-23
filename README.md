# SolarSystemSensor

Read-only Python collector for a Studer Xcom-232i/XCOM installation. The
collector reads documented SCOM data, normalizes it, and sends it to the
Essência [DataHub](https://github.com/Essencia-life/DataHub).

## Observed hardware profile

The supplied installation photos identify this equipment:

- Studer Xtender **XTH-8000-48** hybrid inverter/charger
- Studer **VarioString** dual-isolated-string MPPT solar charge controller
- Studer **RCC-02** remote control centre
- PV1/PV2 inputs and a 48 V battery connection on the Xtender

This is a visual inventory, not proof of the active communication topology.
The photos do not show an Xcom-232i, the RS-232 adapter, the bus wiring, or
device addresses. Confirm those separately before enabling polling.

## Where data is stored

The DataHub is the system of record. Its `studer-xcom` endpoint validates each
metric and stores it in the DataHub PostgreSQL/TimescaleDB
`sensor_measurements` table. SolarSystemSensor does **not** maintain a second
telemetry database.

The only local database is the bounded SQLite **delivery spool**. It contains
payloads that could not yet be delivered, preserves their original capture
timestamps, survives service restarts, and removes records after successful
delivery. It is a reliability buffer, not the historical data store.

## DataHub contract

The collector sends:

```http
POST {DATAHUB_URL}/api/ingest/studer-xcom
x-api-key: {DATAHUB_API_KEY}
Content-Type: application/json
```

```json
{
  "deviceId": "essencia-studer-01",
  "timestamp": "2026-09-23T16:42:00Z",
  "values": [
    { "metric": "battery_voltage_v", "value": 51.2, "unit": "V" }
  ]
}
```

The current DataHub returns HTTP `200` for successful ingestion, `400` for
validation errors, `401` for an invalid API key, and `500` for server errors.
Non-2xx responses are treated as delivery failures and remain in the local
spool for retry. The DataHub API key is never logged or committed.

## Protocol boundary

The repository does not invent Studer command IDs, addresses, property
definitions, scaling factors, or hardware pinouts. Those values must come
from the official Studer documentation for the installed firmware. The
transport and framing code is configurable and read-only, but the
firmware-specific response decoder still requires the documented SCOM mapping.
Do not treat passing mocked tests as proof that a particular Xcom/device
combination is compatible.

## Development

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

The test suite covers framing, transport, normalization, DataHub requests,
device discovery, SQLite spool persistence, and service orchestration. The
CLI is installed as `studer-sensor`.

## Configuration and service

`studer-sensor` runs the polling loop and handles SIGINT/SIGTERM gracefully.
Configure it with [deploy/studer-sensor.env.example](deploy/studer-sensor.env.example):

- serial connection: `SERIAL_PORT`, `SERIAL_BAUDRATE`, `SERIAL_TIMEOUT`
- documented read-only query: `SCOM_QUERY_HEX`
- DataHub: `DATAHUB_URL`, `DATAHUB_API_KEY`, `DATAHUB_TIMEOUT`
- identity/timing: `DEVICE_ID`, `POLL_INTERVAL`
- local reliability: `SPOOL_PATH`
- logging: `LOG_LEVEL`

`DATAHUB_URL` is the DataHub base URL; the client appends
`/api/ingest/studer-xcom`. `SCOM_QUERY_HEX` must be supplied from the official
protocol documentation. `--once` runs one controlled collection cycle.

## Raspberry Pi deployment

See [docs/INSTALL.md](docs/INSTALL.md),
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md), and
[deploy/systemd/studer-sensor.service](deploy/systemd/studer-sensor.service).
Run the service as a dedicated non-root user with access only to the serial
device and spool directory. Hardware wiring, serial settings, and the complete
hardware-to-DataHub path still require manual verification.
