# Installation and operations

The collector is intentionally read-only: it only sends READ_PROPERTY requests
and never writes device settings. The framing (`studer_sensor/scom.py`) follows
`docs/Technical specification - Xtender serial protocol - V1.5.16.pdf`; the
info numbers come from
`docs/Technical specification - Xtender serial protocol appendix - V1.6.40.pdf`.

Order of work: connect the hardware (1), install the software on the Pi (2),
configure (3), do a first single read (4), then enable the service (5).

## 1. Connect the hardware

The Xcom-232i sits on the Studer communication bus (same bus as the RCC) and
talks RS-232 to the Raspberry Pi. It only answers once it is on the bus.

### Xcom-232i on the bus

- Use a free bus port (labelled "CAN" in the Xcom manual) and the same type of
  cable that already links the other devices. Never plug the RS-232 side into a
  bus port or the other way round.
- **Termination:** exactly the two devices at the two ends of the bus have their
  termination switch on `T`; all devices in between are on `O`.
  - Xcom at the end of the chain (one cable): Xcom `T`, and the device that was
    the end before goes to `O`.
  - Xcom in the middle (two cables): Xcom `O`, the existing end devices stay.
  - The Xcom manual contradicts itself about the factory setting, so always
    check the switch. A wrong setting can make the whole bus run erratically.
- Installation work belongs to a qualified person who knows the local rules. The
  manual only asks to switch the Xtenders off for SD-card updates; it does not
  say whether plugging cables in while the system runs is intended. Ask your
  installer or Studer support and pick a moment where a short outage is fine.
- LED on the Xcom: green with two blinks is normal operation; **green blinking
  at 20 % duty means RS-232 traffic**, i.e. the Pi is talking to it. Red means
  update/error/SD card full (see the manual).

### Xcom-232i to the Pi

- The Xcom has a DE-9 **female** RS-232 connector. Only RxD (pin 2), TxD (pin 3)
  and GND (pin 5) are connected; the port is isolated (500 V DC) from the battery.
- The spec prescribes a **straight** cable female to male ("Female-Male,
  straight", spec section 2.2). Use it with a USB-RS232 adapter that has a male
  DE-9 plug (FTDI or PL2303 chips work). If your adapter has a female socket you
  need a null-modem adapter in between.
- The line settings are fixed by the device: **38400 baud, 8 data bits, even
  parity, 1 stop bit** (spec section 3.1). Nothing to configure on the Xcom.
  The baud rate is simply the transmission speed in bits per second; both ends
  must use the same one, which is why the software defaults to 38400 8E1.

## 2. Install on the Raspberry Pi

Create a dedicated unprivileged account, fetch the code and install it into a
virtual environment owned by that account:

```sh
sudo useradd --system --home /var/lib/studer-sensor --shell /usr/sbin/nologin studer-sensor
sudo install -d -o studer-sensor -g studer-sensor /opt/studer-sensor /var/lib/studer-sensor /etc/studer-sensor
sudo -u studer-sensor git clone https://github.com/Essencia-life/SolarSystemSensor.git /opt/studer-sensor/src
sudo -u studer-sensor python3 -m venv /opt/studer-sensor/.venv
sudo -u studer-sensor /opt/studer-sensor/.venv/bin/pip install -r /opt/studer-sensor/src/requirements.txt
sudo -u studer-sensor /opt/studer-sensor/.venv/bin/pip install /opt/studer-sensor/src
```

The last command is required: it provides the `studer-sensor` command that the
systemd unit starts. Check the unit tests once:

```sh
cd /opt/studer-sensor/src && sudo -u studer-sensor /opt/studer-sensor/.venv/bin/python -m pytest -q
```

Give the service account access to the serial port (do not run as root) and find
the adapter:

```sh
sudo usermod -aG dialout studer-sensor
ls -l /dev/serial/by-id/        # stable name of the adapter, points to /dev/ttyUSB0
```

## 3. Configure

```sh
sudo cp /opt/studer-sensor/src/deploy/studer-sensor.env.example /etc/studer-sensor/studer-sensor.env
sudo chown studer-sensor:studer-sensor /etc/studer-sensor/studer-sensor.env
sudo chmod 600 /etc/studer-sensor/studer-sensor.env
sudoedit /etc/studer-sensor/studer-sensor.env
```

Set at least `SERIAL_PORT` (preferably the `/dev/serial/by-id/...` path),
`DEVICE_ID`, `DATAHUB_URL` and `DATAHUB_API_KEY`. API keys must only be supplied
via this file or an equivalent secret manager.

### Which values are read

The protocol has no bulk read: every value is one request/response pair
(`READ_PROPERTY`, user info object). `SCOM_INFOS` lists them as `address:info`
pairs, e.g. `101:3000` is the battery voltage of the first Xtender.

- Addresses: Xtender 101-109, VarioTrack 301-315, BSP 601, VarioString 701-715.
- Info numbers: Xtender 3xxx, BSP 7xxx, VarioTrack 11xxx, VarioString 15xxx
  (V1.6.40 appendix). Enumerations not in the built-in catalog need a format
  suffix, e.g. `101:3010:ENUM`.
- Without `SCOM_INFOS` the first Xtender's battery, AC input and output values
  are read.
- Metrics are named `<device>_<name>_<unit>` (e.g. `xt1_battery_voltage_v`).
  Power the device reports in kW is sent in W (`701:15010` becomes
  `vs1_pv_power_w`).
- A value that cannot be read (device missing, timeout) is logged and skipped.
  NaN values (BSP remaining autonomy while charging) are skipped as well.

## 4. First single read

Start with one value only, with debug logging, as the service user:

```sh
sudo -u studer-sensor sh -c 'set -a; . /etc/studer-sensor/studer-sensor.env; set +a; \
  SCOM_INFOS=101:3000 LOG_LEVEL=DEBUG /opt/studer-sensor/.venv/bin/studer-sensor --once'
```

Success means: no `ERROR`/`WARNING` lines, the Xcom LED blinks green (20 %)
during the call, and `xt1_battery_voltage_v` shows up in the DataHub. The
command prints nothing on success and exits with 0 even if reading failed, so
judge by the log and the DataHub. Compare the voltage with the RCC display.
Then extend `SCOM_INFOS` step by step, e.g.
`101:3000,601:7002,701:15004,701:15010`.

| Log message | Likely cause |
|---|---|
| `expected 14 bytes, got 0` (timeout) | Nothing answers: Xcom not on the bus or not powered, wrong port, cable/adapter gender, RxD/TxD swapped (try a null-modem adapter), wrong `SERIAL_PORT` |
| `bad start byte`, `checksum mismatch` | Garbage on the line: bad cable/adapter, interference; settings must be 38400 8E1 |
| `SCOM error DEVICE_NOT_FOUND` | No device at that address (e.g. no BSP at 601) |
| `SCOM error OBJECT_ID_NOT_FOUND` | The device or firmware does not offer that info |
| `Permission denied` on the port | Account not in `dialout`; log in again after `usermod` |
| `DataHub delivery failed` | URL, TLS, API key; records stay in the spool and are retried |

## 5. systemd

`DeviceAllow` in `deploy/systemd/studer-sensor.service` must name the real device
node (`/dev/ttyUSB0`, not the by-id link). Adjust it if the adapter has another
number, then:

```sh
sudo cp /opt/studer-sensor/src/deploy/systemd/studer-sensor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now studer-sensor
journalctl -u studer-sensor -f
```

Restrict the DataHub key and the SQLite directory to the service account.

## Update and recovery

Stop the service, update the code and reinstall into the same virtual
environment, run the tests, then start it again:

```sh
sudo systemctl stop studer-sensor
sudo -u studer-sensor git -C /opt/studer-sensor/src pull
sudo -u studer-sensor /opt/studer-sensor/.venv/bin/pip install /opt/studer-sensor/src
sudo systemctl start studer-sensor
```

The SQLite spool survives process restarts and DataHub outages; pending records
are retried with exponential backoff. Back up the spool database before upgrades
if telemetry durability is important.
