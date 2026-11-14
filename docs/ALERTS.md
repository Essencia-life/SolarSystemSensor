# Grafana alert rules (proposal)

Create these in Grafana Cloud under Alerting > Alert rules > New alert rule, data source Prometheus.
All thresholds are assumptions for a 48 V lead-acid bank: adjust them once the shutdown voltage
(`xt1_low_voltage_disconnect_v`) and the real voltage range under load are known.
The notification channel (e-mail, Telegram, ...) is configured under Alerting > Contact points.

| Rule | Query (PromQL) | Condition | Pending period |
|---|---|---|---|
| No data | `absent_over_time(datahub_xt1_battery_voltage_v[15m])` | is above 0 | 0 m |
| Battery low | `last_over_time(datahub_xt1_battery_voltage_v[15m])` | is below 46 | 10 m |
| Close to shutdown | `sum by (device_id) (last_over_time(datahub_xt1_battery_voltage_v[15m])) - sum by (device_id) (last_over_time(datahub_xt1_low_voltage_disconnect_v[15m]))` | is below 2 | 5 m |

Notes:

- **No data** is the only rule that still fires when the Raspberry Pi or the Studer bus is dead: it
  reacts to missing samples, not to a value. Set "Alert state if no data" to "Alerting" for the
  other two rules as well if a silent Pi should be reported.
- **Battery low** uses a pending period of 10 minutes so that short voltage sags under load
  (down to 45 V were seen) do not trigger it. Shorten it if that is too slow.
- **Close to shutdown** needs `101:3008` in `SCOM_INFOS`. A rule on the voltage alone is the
  fallback if that value cannot be read.
- Rules fire only while samples arrive. During a low voltage shutdown the Pi needs its own power
  (UPS or DC supply) to keep reporting.
