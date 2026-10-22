# Tracked values

Every value is sent as `{metric, value, unit}` to `POST /api/ingest/studer-xcom`.
The DataHub forwards it to Grafana Cloud (live, series `datahub_<metric>` with the
labels `device_id`, `sensor`, `source`, `unit`) and archives it in the table
`sensor_measurements` (5-minute values, see the DataHub README). Metric names follow
`<device>_<name>_<unit>`: `xt1` = Xtender 101, `vs1` = VarioString 701,
`bsp` = BSP 601. Power reported in kW is converted to W before sending.
Info numbers come from the protocol appendix V1.6.40; address 101 = Xtender,
701 = VarioString, 601 = BSP.

## 1. Read so far (default list, as long as `SCOM_INFOS` was not changed)

First Xtender (101) only. The code default interval is 30 s, the Pi runs with `POLL_INTERVAL=60`.

| Address:info | DataHub metric name | Unit | Meaning |
|---|---|---|---|
| `101:3000` | `xt1_battery_voltage_v` | V | Battery voltage |
| `101:3005` | `xt1_battery_charge_current_a` | A | Battery current (negative = discharging) |
| `101:3011` | `xt1_input_voltage_v` | V | AC input voltage |
| `101:3012` | `xt1_input_current_a` | A | AC input current |
| `101:3021` | `xt1_output_voltage_v` | V | AC output voltage |
| `101:3022` | `xt1_output_current_a` | A | AC output current |
| `101:3087` | `xt1_output_active_power_w` | W | AC output power (less accurate than 3136) |
| `101:3088` | `xt1_input_active_power_w` | W | AC input power (less accurate than 3137) |

## 2. New in `deploy/studer-sensor.env.example` (off-grid, without BSP and BTS)

Interval 60 s. On the Pi this only takes effect after `SCOM_INFOS` and
`POLL_INTERVAL` are copied into `/etc/studer-sensor/studer-sensor.env` and the
service is restarted. The old values from section 1 stay unless replaced:
3087 is replaced by 3136, 3088 by 3137, and 3021 (output voltage) is dropped.

Xtender:

| Address:info | DataHub metric name | Unit | Meaning |
|---|---|---|---|
| `101:3000` | `xt1_battery_voltage_v` | V | Battery voltage |
| `101:3005` | `xt1_battery_charge_current_a` | A | Battery current (negative = discharging) |
| `101:3136` | `xt1_output_active_power_w` | W | Consumption (AC output); replaces 3087 |
| `101:3022` | `xt1_output_current_a` | A | AC output current |
| `101:3028` | `xt1_operating_state` | enum | Xtender operating state |
| `101:3010` | `xt1_battery_cycle_phase` | enum | Battery charge phase (bulk / absorption / float ...) |
| `101:3083` | `xt1_consumers_energy_today_kwh` | kWh | Consumption today |
| `101:3078` | `xt1_battery_discharge_today_kwh` | kWh | Battery discharge today |
| `101:3045` | `xt1_overload_count` | - | Overload counter |
| `101:3011` | `xt1_input_voltage_v` | V | AC input voltage |
| `101:3012` | `xt1_input_current_a` | A | AC input current |
| `101:3137` | `xt1_input_active_power_w` | W | Generator / AC input power; replaces 3088 |
| `101:3081` | `xt1_energy_from_today_kwh` | kWh | Energy from the AC source (generator) today |
| `101:3020` | `xt1_transfer_relay` | enum | Transfer relay (generator connected through?) |

VarioString (PV):

| Address:info | DataHub metric name | Unit | Meaning |
|---|---|---|---|
| `701:15004` | `vs1_pv_voltage_v` | V | PV voltage |
| `701:15010` | `vs1_pv_power_w` | W | PV power (kW converted to W) |
| `701:15017` | `vs1_production_kwh_today_kwh` | kWh | PV yield today |
| `701:15108` | `vs1_state` | enum | VarioString state |

Note on the generator: the input values (3011, 3012, 3137, 3081, 3020) only show
something if the generator really feeds the Xtender's AC input. How it is
connected has not been clarified yet and should be checked by someone who knows
the electrical distribution.

Metrics with unit `enum` or `-` in the tables above have no unit: they are sent with
`"unit": null` and appear in Grafana without the `unit` label. In the archive they keep
the last value of each 5-minute bucket (average would be meaningless for states); the
same holds for the "today" energy counters. All other metrics are averaged.

## 3. Later, if hardware is added

| Address:info | DataHub metric name | Unit | Meaning |
|---|---|---|---|
| `601:7002` | `bsp_state_of_charge_pct` | % | BSP only: state of charge |
| `601:7004` | `bsp_remaining_autonomy_min` | min | BSP only: remaining autonomy (NaN while charging, skipped) |
| `601:7005` | `bsp_temperature_c` | °C | BSP only: battery temperature |
| `601:7007` | `bsp_ah_charged_today_ah` | Ah | BSP only: Ah charged today |
| `101:3001` | `xt1_battery_temperature_c` | °C | BTS only: battery temperature |
| `101:3007` | `xt1_state_of_charge_pct` | % | BSP only: state of charge (via Xtender) |

Without a BSP and a BTS there is no real state of charge and no battery
temperature. Battery voltage and current, charge phase and daily PV yield are
then the best indicators of battery health.

## Grafana ideas

In Grafana every name below has the prefix `datahub_`, e.g. `datahub_xt1_battery_voltage_v`.

- Minimum of `xt1_battery_voltage_v` per night (trend = capacity loss)
- Voltage sag at high negative `xt1_battery_charge_current_a` (discharging under load)
- Does `xt1_battery_cycle_phase` still reach absorption/float?
- `vs1_production_kwh_today_kwh` against `xt1_consumers_energy_today_kwh`
- Generator run time from `xt1_input_active_power_w` > 0
