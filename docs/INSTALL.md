# Installation and operations

The collector is intentionally read-only: it only sends READ_PROPERTY requests
and never writes device settings. The framing (`studer_sensor/scom.py`) follows
`docs/Technical specification - Xtender serial protocol - V1.5.16.pdf`:
38400 baud, 8 data bits, even parity, 1 stop bit (set `SERIAL_BAUDRATE` to whatever the Xcom-232i is configured for).

## Which values are read

The protocol has no bulk read: every value is one request/response pair
(`READ_PROPERTY`, user info object). `SCOM_INFOS` lists them as
`address:info` pairs, e.g. `101:3000` is the battery voltage of the first
Xtender (addresses: Xtender 101-109, VarioTrack 301-315, BSP 601, VarioString 701-715;
info numbers: Xtender 3xxx, BSP 7xxx, VarioTrack 11xxx, VarioString 15xxx in the
V1.6.40 appendix). Without `SCOM_INFOS` the first Xtender's
battery, AC input and output values are read. Metrics are named
`<device>_<name>_<unit>` (e.g. `xt1_battery_voltage_v`). A value that cannot be read
(device missing, timeout) is logged and skipped. Power values the device reports in kW are sent in W (e.g. `701:15010` becomes
`vs1_pv_power_w`). NaN values (BSP remaining autonomy while charging) are skipped.
Enumerations need a format
suffix when the info is not in the built-in catalog, e.g. `101:3010:ENUM`.

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
