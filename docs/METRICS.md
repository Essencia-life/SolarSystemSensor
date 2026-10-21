# Getrackte Werte

Alle Werte gehen als `{metric, value, unit}` an `POST /api/ingest/studer-xcom`
und landen in der DataHub-Tabelle `sensor_measurements`. Der Metrikname folgt
`<Gerät>_<Name>_<Einheit>`: `xt1` = Xtender 101, `vs1` = VarioString 701,
`bsp` = BSP 601. Leistung in kW wird vor dem Senden in W umgerechnet.
Die Info-Nummern stammen aus dem Appendix V1.6.40; Adresse 101 = Xtender,
701 = VarioString, 601 = BSP.

## 1. Bisher gelesen (Standardliste, solange `SCOM_INFOS` nicht angepasst war)

Nur der erste Xtender (101), Standardintervall 30 s (auf dem Pi evtl. schon auf 300 s gestellt).

| Adresse:Info | DB-Metrikname (`metric`) | Einheit | Bedeutung |
|---|---|---|---|
| `101:3000` | `xt1_battery_voltage_v` | V | Batteriespannung |
| `101:3005` | `xt1_battery_charge_current_a` | A | Batteriestrom (negativ = Entladung) |
| `101:3011` | `xt1_input_voltage_v` | V | AC-Eingangsspannung |
| `101:3012` | `xt1_input_current_a` | A | AC-Eingangsstrom |
| `101:3021` | `xt1_output_voltage_v` | V | AC-Ausgangsspannung |
| `101:3022` | `xt1_output_current_a` | A | AC-Ausgangsstrom |
| `101:3087` | `xt1_output_active_power_w` | W | AC-Ausgangsleistung (ungenauer als 3136) |
| `101:3088` | `xt1_input_active_power_w` | W | AC-Eingangsleistung (ungenauer als 3137) |

## 2. Neu in `deploy/studer-sensor.env.example` (Off-Grid, ohne BSP und BTS)

Intervall 300 s. Auf dem Pi erst aktiv, wenn `SCOM_INFOS` und `POLL_INTERVAL`
in `/etc/studer-sensor/studer-sensor.env` übernommen und der Dienst neu gestartet
wurde. Die alten Werte aus Abschnitt 1 bleiben in der neuen Liste, soweit sie
nicht ersetzt sind (3000, 3005, 3011, 3012, 3022). Ersetzt wird 3087 durch 3136 und
3088 durch 3137; 3021 (Ausgangsspannung) entfällt.

Xtender:

| Adresse:Info | DB-Metrikname (`metric`) | Einheit | Bedeutung |
|---|---|---|---|
| `101:3000` | `xt1_battery_voltage_v` | V | Batteriespannung |
| `101:3005` | `xt1_battery_charge_current_a` | A | Batteriestrom (negativ = Entladung) |
| `101:3136` | `xt1_output_active_power_w` | W | Verbrauch (AC-Ausgang), ersetzt 3087 |
| `101:3022` | `xt1_output_current_a` | A | AC-Ausgangsstrom |
| `101:3028` | `xt1_operating_state` | Enum | Betriebszustand Xtender |
| `101:3010` | `xt1_battery_cycle_phase` | Enum | Ladephase Batterie (Bulk/Absorption/Float ...) |
| `101:3083` | `xt1_consumers_energy_today_kwh` | kWh | Verbrauch heute |
| `101:3078` | `xt1_battery_discharge_today_kwh` | kWh | Batterieentladung heute |
| `101:3045` | `xt1_overload_count` | – | Zähler Überlastungen |
| `101:3011` | `xt1_input_voltage_v` | V | AC-Eingangsspannung (Generator) |
| `101:3012` | `xt1_input_current_a` | A | AC-Eingangsstrom (Generator) |
| `101:3137` | `xt1_input_active_power_w` | W | Generator-/Eingangsleistung, ersetzt 3088 |
| `101:3081` | `xt1_energy_from_today_kwh` | kWh | Energie aus Quelle (Generator) heute |
| `101:3020` | `xt1_transfer_relay` | Enum | Transferrelais (Generator durchgeschaltet?) |

VarioString (PV):

| Adresse:Info | DB-Metrikname (`metric`) | Einheit | Bedeutung |
|---|---|---|---|
| `701:15004` | `vs1_pv_voltage_v` | V | PV-Spannung |
| `701:15010` | `vs1_pv_power_w` | W | PV-Leistung (kW->W) |
| `701:15017` | `vs1_production_kwh_today_kwh` | kWh | PV-Tagesertrag |
| `701:15108` | `vs1_state` | Enum | VarioString-Zustand |

Hinweis zum Generator: Die Eingangswerte (3011, 3012, 3137, 3081, 3020) zeigen nur
dann etwas, wenn der Generator wirklich am AC-Eingang des Xtenders hängt. Wie
er angeschlossen ist, ist noch nicht geklärt und sollte von jemandem geprüft
werden, der die Verteilung kennt.

## 3. Später, falls Hardware nachgerüstet wird

| Adresse:Info | DB-Metrikname (`metric`) | Einheit | Bedeutung |
|---|---|---|---|
| `601:7002` | `bsp_state_of_charge_pct` | % | nur mit BSP: Ladezustand |
| `601:7004` | `bsp_remaining_autonomy_min` | min | nur mit BSP: Restlaufzeit (NaN beim Laden, wird übersprungen) |
| `601:7005` | `bsp_temperature_c` | °C | nur mit BSP: Batterietemperatur |
| `601:7007` | `bsp_ah_charged_today_ah` | Ah | nur mit BSP: Ah geladen heute |
| `101:3001` | `xt1_battery_temperature_c` | °C | nur mit BTS: Batterietemperatur |
| `101:3007` | `xt1_state_of_charge_pct` | % | nur mit BSP: Ladezustand (Xtender) |

Ohne BSP und BTS gibt es keinen echten Ladezustand und keine Batterietemperatur.
Dann sind Batteriespannung und -strom, Ladephase und PV-Tagesertrag die besten
Indikatoren für den Batteriezustand.

## Auswertungen für Grafana (Ideen)

- Minimum von `xt1_battery_voltage_v` pro Nacht (Trend = Kapazitätsverlust)
- Spannungseinbruch bei hohem `xt1_battery_charge_current_a` im Minus
- Erreicht `xt1_battery_cycle_phase` noch Absorption/Float?
- `vs1_production_kwh_today_kwh` gegen `xt1_consumers_energy_today_kwh`
- Generatorlaufzeit aus `xt1_input_active_power_w` > 0
