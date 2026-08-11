# Preliminary power budget

Values below are design targets, not final measurements. Prototype bring-up
must verify regulator temperature, battery current and RF noise in every mode.

## Regulator targets

| Rail | Continuous target | Short peak target | Notes |
|---|---:|---:|---|
| +3V3 | 1.5 A | 2.0 A | ESP32 Wi-Fi, NFC, storage and radios |
| +5V_RAW total | 1.0 A | 1.5 A | IR, RGB plus TPS2553/header branch |
| +5V_AUX header | 0.5 A | 0.5 A | Hardware current limit required |
| LiPo discharge | 2.0 A | 3.0 A | Recommended minimum pack capability |

## Approximate peak loads

| Load | Rail | Approximate peak allocation |
|---|---:|---:|
| ESP32-S3 Wi-Fi TX | 3.3 V | 360 mA |
| PN532 RF field | 3.3 V | 170 mA |
| microSD write transient | 3.3 V | 200 mA |
| Four RGB LEDs, full white | 5 V | 240 mA |
| CC1101 transmit | 3.3 V | 40 mA |
| HTRC110 logic plus antenna bridge | 5 V | up to about 140 mA; measure final coil |
| Sensors, RTC, expanders and OLED | 3.3 V | 100 mA |
| Board-temperature divider | 3.3 V | about 0.17 mA at 25 degrees C |
| IR transmitter, current V1 default | 5 V | approximately 100 mA pulsed |

The allocations do not all occur continuously. The 3.3-V rail is nevertheless
sized for their transient sum with local bulk capacitance near the ESP32,
PN532, microSD and radio sections.

The RGB chain is supplied by `+5V_RAW`, not by 3.3 V. A
SN74AHCT1G126 level shifter translates `RGB_DATA`; its active-high output
enable follows `BOOST5_EN`, so the LED data pin is not back-powered while the
5-V rail is disabled. Firmware must include the four LEDs in the shared
5-V-load budget.

## Battery recommendation

- Protected single-cell LiPo, 3.7 V nominal and 4.2 V charge voltage
- 1000-2000 mAh for practical mobile use
- At least 2 A continuous and 3 A pulse discharge capability
- Correctly wired two-pin connector; polarity must be checked before use

The configured charge-current target is 500 mA, but the charger starts in its
USB100 state. Firmware may select USB500 only after the source/current contract
allows it. The BQ24074 power path allows the card to operate while charging and
lets the battery supplement short load peaks.

## Firmware limits

- Do not allow high-power IR and an unrestricted 5 V external load together.
- Reduce RGB brightness during IR boost operation.
- Disable 5 V after a configurable inactivity timeout.
- Reject IR boost mode below a configurable battery threshold.
- Flush microSD data before deep sleep or power-domain shutdown.
- Record brownout and overtemperature events in a persistent diagnostic log.
- At 80 degrees C board temperature, stop charging and all switchable 5-V
  loads; require cooling below 70 degrees C before releasing the charger.
