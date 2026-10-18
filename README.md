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

Framing, addresses and info numbers come from
[docs/Technical specification - Xtender serial protocol - V1.5.16.pdf](docs/Technical%20specification%20-%20Xtender%20serial%20protocol%20-%20V1.5.16.pdf)
(`studer_sensor/scom.py`); only the read-only `READ_PROPERTY` service is
implemented, one request per value. The tests check the spec's example frames
byte for byte, but passing tests are no proof that a particular Xcom/device
combination works: verify against the real hardware first (`--once`). That
spec revision lists Xtender, BSP, VarioTrack and Xcom-MS; it does not list the
VarioString, so its PV data may need a newer spec.

## Development

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

The test suite covers SCOM framing and checksums (including the spec's example
frames), transport, normalization, DataHub requests, device discovery, SQLite
spool persistence, and service orchestration. The CLI is installed as
`studer-sensor`.

## Configuration and service

`studer-sensor` runs the polling loop and handles SIGINT/SIGTERM gracefully.
Configure it with [deploy/studer-sensor.env.example](deploy/studer-sensor.env.example):

- serial connection: `SERIAL_PORT`, `SERIAL_BAUDRATE` (38400), `SERIAL_PARITY` (E), `SERIAL_TIMEOUT`
- values to read: `SCOM_INFOS` (`address:info` pairs, see [docs/INSTALL.md](docs/INSTALL.md)), `SCOM_SRC_ADDR`
- DataHub: `DATAHUB_URL`, `DATAHUB_API_KEY`, `DATAHUB_TIMEOUT`
- identity/timing: `DEVICE_ID`, `POLL_INTERVAL`
- local reliability: `SPOOL_PATH`
- logging: `LOG_LEVEL`

`DATAHUB_URL` is the DataHub base URL; the client appends
`/api/ingest/studer-xcom`. `--once` runs one controlled collection cycle.
Metric names follow the DataHub convention `<device>_<name>_<unit>`, e.g.
`xt1_battery_voltage_v`, `bsp_state_of_charge_pct`.

## Raspberry Pi deployment

See [docs/INSTALL.md](docs/INSTALL.md),
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md), and
[deploy/systemd/studer-sensor.service](deploy/systemd/studer-sensor.service).
Run the service as a dedicated non-root user with access only to the serial
device and spool directory. Hardware wiring, serial settings, and the complete
hardware-to-DataHub path still require manual verification.

For the initial Raspberry Pi network setup, see
[docs/raspi-netzwerk-setup-stefan-ben.md](docs/raspi-netzwerk-setup-stefan-ben.md).
