# Preliminary power budget

Values below are design targets, not final measurements. Prototype bring-up
must verify regulator temperature, battery current and RF noise in every mode.

## Regulator targets

| Rail | Continuous target | Short peak target | Notes |
|---|---:|---:|---|
| +3V3 | 1.5 A | 2.0 A | ESP32 Wi-Fi, NFC, storage and radios |
| +5V_AUX total | 1.0 A | 1.5 A | IR plus protected external output |
| +5V_AUX header | 0.5 A | 0.5 A | Hardware current limit required |
| LiPo discharge | 2.0 A | 3.0 A | Recommended minimum pack capability |

## Approximate peak loads

| Load | Rail | Approximate peak allocation |
|---|---:|---:|
| ESP32-S3 Wi-Fi TX | 3.3 V | 360 mA |
| PN532 RF field | 3.3 V | 170 mA |
| microSD write transient | 3.3 V | 200 mA |
| Four RGB LEDs, full white | 3.3 V | 240 mA |
| CC1101 transmit | 3.3 V | 40 mA |
| GNSS plus active antenna | 3.3 V | 50 mA |
| Sensors, RTC, expander, buzzer | 3.3 V | 80 mA |
| High-power IR | 5 V | 100-800 mA pulsed |

The 3.3 V allocations do not all occur continuously. The rail is nevertheless
sized for their transient sum with local bulk capacitance near the ESP32,
PN532, microSD and radio sections.

## Battery recommendation

- Protected single-cell LiPo, 3.7 V nominal and 4.2 V charge voltage
- 1000-2000 mAh for practical mobile use
- At least 2 A continuous and 3 A pulse discharge capability
- Correctly wired two-pin connector; polarity must be checked before use

The initial charge current target is 500 mA. This limits board heating and is
appropriate for USB default-current operation. The BQ24074 power path allows
the card to operate while charging and lets the battery supplement short load
peaks.

## Firmware limits

- Do not allow high-power IR and an unrestricted 5 V external load together.
- Reduce RGB brightness during IR boost operation.
- Disable 5 V after a configurable inactivity timeout.
- Reject IR boost mode below a configurable battery threshold.
- Flush microSD data before deep sleep or power-domain shutdown.
- Record brownout and overtemperature events in a persistent diagnostic log.
