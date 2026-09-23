# Installation and operations

The collector is intentionally read-only: it only sends documented telemetry
queries and never writes device settings. Exact SCOM/XCOM command values must
be supplied from official Studer documentation; this software does not guess
undocumented protocol constants.

## Install

Create a dedicated unprivileged account and install into `/opt/studer-sensor`:

```sh
sudo useradd --system --home /var/lib/studer-sensor --shell /usr/sbin/nologin studer-sensor
sudo install -d -o studer-sensor -g studer-sensor /opt/studer-sensor /var/lib/studer-sensor /etc/studer-sensor
python3 -m venv /opt/studer-sensor/.venv
/opt/studer-sensor/.venv/bin/pip install -r requirements.txt
```

Copy `deploy/studer-sensor.env.example` to `/etc/studer-sensor/studer-sensor.env`,
set values, and protect it (`chmod 600`). API keys must only be supplied via
the environment file or an equivalent secret manager.

## systemd

Adjust `DeviceAllow` in `deploy/systemd/studer-sensor.service` for the actual
USB serial device, then:

```sh
sudo cp deploy/systemd/studer-sensor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now studer-sensor
journalctl -u studer-sensor -f
```

Grant the service account access to the serial device using the distribution's
`dialout` (or equivalent) group, rather than running the service as root.
Restrict the DataHub key and SQLite directory permissions to this account.

## Update and recovery

Stop the service, install the new package into the same virtual environment,
run the test suite, then start it again. The SQLite spool survives process
restarts and DataHub outages; pending records are retried with exponential
backoff. Back up the spool database before upgrades if telemetry durability is
important.
