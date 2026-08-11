# PocketLab Card firmware

This directory contains the buildable ESP32-S3 baseline for hardware revision
1. It targets the ESP32-S3-WROOM-1-N8R2 (8 MB flash, 2 MB quad PSRAM) with
Arduino-ESP32 3.x and PlatformIO.

## Implemented baseline

- WPA2 Wi-Fi SoftAP with a local, mobile-friendly web interface
- REST status/configuration endpoints and a read-only WebSocket status stream
- microSD mount, directory listing, download, upload, deletion and remount
- checksum-validated NMEA RMC/GGA parser on the GNSS UART
- CSV trip logging with UTC, coordinates, speed, course, altitude, satellites
  and HDOP; live distance and point counters are shown in the web UI
- safe boot states for CC1101, microSD, IR, RGB and all exposed GPIOs
- read-only CC1101 identity probe, PN532 I2C presence probe, TCA9535 status
  inputs and TCA9534 control/button status
- GNSS power control through the dedicated TCA9534 control expander, explicit
  conflict checks around an active trip, and UART high-impedance sequencing so
  an unpowered MAX-M10S is not driven through GPIO35
- authenticated NEC IR transmission through the three shared emitters, with a
  38.5 kHz software carrier, a 150 ms request interval and at most two repeats

The implementation is intentionally a bring-up baseline. It does not yet
contain PN532 transactions, CC1101 receive/decoding, IR decoding, sensor
drivers, battery telemetry or Sub-GHz transmission.

## Build and upload

From this directory:

```powershell
pio run
pio run -t upload
pio device monitor
```

The validated build uses PlatformIO Core 6.1.19, Arduino-ESP32 3.3.8 and
WebSockets 2.7.3. The current release build consumes approximately 49.7 kB RAM
and 1.13 MB application flash. Actual values can change with the toolchain.

At boot, USB CDC prints the access point credentials and URL. Credentials are
deterministically derived from the ESP32 eFuse ID:

- SSID: `PocketLab-XXXXXX`
- password: `PL-XXXXXXXX`
- URL: `http://192.168.4.1/`

This per-device password is suitable for local prototype bring-up, but it is
not a replacement for a user-set secret in a production device.

## Safety policy

`platformio.ini` enables only the bounded IR remote-control path:

```ini
-DPOCKETLAB_ALLOW_SUBGHZ_TX=0
-DPOCKETLAB_ALLOW_IR_TX=1
-DPOCKETLAB_ALLOW_GPIO_OUTPUT=0
```

Sub-GHz transmission and arbitrary GPIO output have no implementation and
remain locked. WebSocket input is read-only, the 5 V boost starts disabled,
IR starts low, and the twelve direct expansion GPIOs remain inputs. The IR
endpoint accepts only an 8-bit NEC address, an 8-bit command and zero to two
repeats; it temporarily enables the 5 V rail and restores its prior state.

Future radio work must add an explicit physical/user authorization flow,
regional frequency and duty-cycle limits, bounded power, and tests before a TX
path is merged. Do not automate replay or transmission of captured traffic.

## HTTP and WebSocket interface

Read-only endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Minimal liveness response |
| `GET` | `/api/config` | WebSocket port and boot-session mutation token |
| `GET` | `/api/status` | Combined Wi-Fi, hardware, storage and GNSS status |
| `GET` | `/api/hardware` | Hardware probes and compile-time policy |
| `GET` | `/api/gpio` | Direct GPIO and TCA9535 `EX0`-`EX7` levels, input-only |
| `GET` | `/api/files?path=/trips` | Directory listing |
| `GET` | `/api/file?path=/trips/example.csv` | File download |

Mutating endpoints require the current `X-PocketLab-Token` header. The same
origin web UI obtains it from `/api/config`; it changes on every boot.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/trip/start` | Enable GNSS if possible and start CSV logging |
| `POST` | `/api/trip/stop` | Flush and close the current CSV file |
| `POST` | `/api/gnss/power?enabled=1` | Switch GNSS power through TCA9534 |
| `POST` | `/api/ir/tx?address=0&command=0&repeats=0` | Send one bounded NEC IR frame |
| `POST` | `/api/sd/remount` | Remount the card while no trip is active |
| `POST` | `/api/upload?path=/uploads/name` | Multipart file upload |
| `DELETE` | `/api/file?path=/uploads/name` | Delete a file or empty directory |

Status WebSocket clients connect to port `81`. The server sends JSON once per
second and rejects all client commands.

## Trip files

Trips are stored below `/trips` as CSV. A valid RMC date/time is used in the
filename; a boot-time fallback is used before the first fix. A random suffix
prevents appending to an old trip with the same timestamp. Valid fixes are
logged at most once per second and flushed every ten points or five seconds.

## Hardware assumptions to verify on the first assembled board

- U9 TCA9535 address `0x20`; P00-P07 are `SD_DETECT_N`, `CHARGER_CHG_N`,
  `CHARGER_PGOOD_N`, `AUX5_FAULT_N`, `FG_ALERT_N`, `BMI_INT1`, `BMI_INT2`
  and `BMP_INT`; P10-P17 are exposed as `EX0`-`EX7` and remain inputs
- U18 TCA9534 address `0x21`; P0-P5 are `BQ_EN1`, `CHG_DISABLE`, `AUX5_EN`,
  `NFC_RESET_N`, `GNSS_POWER_EN` and `BOOST5_EN`; P6/P7 are active-low user
  buttons
- safe U18 boot latch: `BQ_EN1=0` (USB100 with EN2 tied low),
  `CHG_DISABLE=0`, AUX 5 V/GNSS/5 V boost off and PN532 held in reset until
  the expander is configured
- the current firmware deliberately leaves `BQ_EN1=0`; it does not claim
  USB500 without a separately audited source-current/USB-enumeration policy
- PN532 I2C address `0x24`
- MAX-M10S NMEA UART at 9600 baud; UART starts only after `GNSS_POWER_EN` and
  is ended/high-impedance before that rail is switched off
- CC1101 identity (`PARTNUM=0x00`, nonzero/non-`0xFF` `VERSION`)
- shared SPI operation with both chip-select idle levels high

`include/board_pins.h` mirrors `docs/pinout.md`. Any schematic pin change must
be applied to both before assembling or flashing hardware.
