# Raspberry Pi: Ethernet und WLAN einrichten

**Für:** Stefan und Ben  
**Ziel:** Den Raspberry Pi zunächst per Ethernet ins Netzwerk bringen und WLAN
einrichten, damit er später mit den weiteren Komponenten verbunden werden kann.

## Vorbereitung

- Raspberry Pi und Netzteil
- Ethernet-Kabel und Zugang zum Router bzw. Switch
- WLAN-Name (SSID) und WLAN-Passwort
- Bei einem headless Pi: ein Rechner im selben Netzwerk für den Fernzugriff

WLAN-Zugangsdaten nicht in dieses Dokument oder ins Git-Repository eintragen.

## Ethernet anschließen und Pi starten

1. Raspberry Pi mit einem Ethernet-Kabel an Router oder Switch anschließen.
2. Pi einschalten und warten, bis Raspberry Pi OS gestartet ist.
3. Im Router die zugewiesene IP-Adresse nachsehen. Alternativ am Pi ausführen:

   ```sh
   hostname -I
   ```

4. Falls der Pi ohne Bildschirm läuft, per SSH aus dem lokalen Netzwerk
   anmelden. SSH muss dafür in Raspberry Pi OS aktiviert sein:

   ```sh
   ssh <benutzername>@<ethernet-ip>
   ```

## WLAN einrichten

### Mit grafischer Oberfläche

1. WLAN-Menü öffnen und das gewünschte Netzwerk auswählen.
2. WLAN-Passwort eingeben und die Verbindung herstellen.
3. Prüfen, dass das WLAN-Menü eine aktive Verbindung anzeigt.

### Ohne grafische Oberfläche

Raspberry Pi OS verwendet NetworkManager. Verfügbare WLAN-Netze anzeigen und
das gewünschte Netzwerk verbinden:

```sh
nmcli device wifi list
nmcli --ask device wifi connect "<SSID>"
```

Das Passwort wird interaktiv abgefragt und muss nicht in der Shell-History
stehen.

## Verbindung prüfen

```sh
ip -br address
nmcli device status
```

Sowohl Ethernet als auch WLAN sollten verbunden sein und jeweils eine
Netzwerkadresse haben. Zusätzlich die Erreichbarkeit des lokalen Netzwerks
prüfen, zum Beispiel mit:

```sh
ping -c 3 <router-ip>
```

Anschließend notieren:

- Pi-Hostname: ____________________
- Ethernet-IP (DHCP): ____________________
- WLAN-IP (DHCP): ____________________
- WLAN-Verbindung erfolgreich: Ja / Nein

## Für die spätere Verbindung mit weiteren Komponenten

- Festhalten, an welchem Router/Switch und WLAN der Pi hängt.
- Prüfen, ob die späteren Komponenten im selben Netzwerk erreichbar sind.
  Gast-WLANs oder Client-Isolation können Verbindungen zwischen Geräten
  verhindern.
- Für dauerhaft erreichbare Dienste bei Bedarf im Router DHCP-Reservierungen
  für Ethernet und WLAN einrichten. Keine statischen IP-Adressen vergeben,
  bevor das Netzwerk und die zuständigen Adressbereiche abgestimmt sind.
- Die Verbindung und die Erreichbarkeit der späteren Komponenten separat
  testen; eine eingerichtete WLAN-Verbindung allein bestätigt noch nicht den
  vollständigen Datenpfad.

## Ergebnis

- [ ] Raspberry Pi startet und ist per Ethernet erreichbar.
- [ ] WLAN ist eingerichtet und verbunden.
- [ ] Ethernet- und WLAN-Adressen sind dokumentiert.
- [ ] Netzwerkdetails und offene Punkte wurden an das Team weitergegeben.
