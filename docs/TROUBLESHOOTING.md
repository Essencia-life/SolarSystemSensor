# Hardware verification and troubleshooting

Software tests use fake serial transports and mocked DataHub responses. They
verify framing, checksums, parsing, normalization, retry, and persistence; they
do **not** prove that a particular Studer device speaks a given command set.
Confirm every command, address, baud rate, and checksum rule against the
official XCOM/SCOM documentation and the installed firmware before connecting
hardware.

## Installation-specific notes

The available photos show an Xtender XTH-8000-48, a VarioString MPPT
controller, an RCC-02 remote control centre, and PV1/PV2 plus 48 V battery
connections. They do not establish that an Xcom-232i is installed or show its
RS-232 wiring. Verify the communication adapter, bus topology, connector
pinout, and device addresses on site.

## Safe first connection

1. Confirm the adapter's voltage/electrical standard and wiring. Do not connect
   an RS-232 adapter to an RS-485/CAN port.
2. Identify the serial device (`udevadm info`, `ls -l /dev/serial/by-id`) and
   grant the service account access without running as root.
3. Start with read-only commands documented for the exact device and capture
   logs. Verify no write/configuration command is enabled in your deployment.
4. Compare one returned value with the local device display, including units and
   timestamp, before enabling unattended collection.

## Common symptoms

- **Permission denied:** add the account to the platform's serial-device group,
  log in again, and check `ls -l` on the device node.
- **Timeouts or checksum errors:** check cabling, termination, port settings,
  framing mode, and documented protocol revision. Do not relax checksum checks
  to make data appear valid.
- **No DataHub delivery:** verify URL, DNS/TLS, API key permissions, and clock
  synchronization. The SQLite spool should retain records while the endpoint
  is unavailable and retry with backoff.
- **Missing telemetry:** metric absence is expected when firmware does not expose
  an optional field. Inspect normalized output and configure only documented
  metrics; a missing value should not crash collection.

See the error table in [INSTALL.md](INSTALL.md#4-first-single-read) for the
log messages of a failing read.

Use `journalctl -u studer-sensor` and the configured spool database metrics to
separate serial acquisition, normalization, and HTTP ingestion failures.
Redact API keys and payload secrets from support logs.
