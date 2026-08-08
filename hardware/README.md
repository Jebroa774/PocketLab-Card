# Hardware design source

## Planned KiCad sheets

| Sheet | Contents |
|---|---|
| 00_ROOT | Power domains, buses and hierarchical connections |
| 01_USB_POWER | USB-C, ESD, charger, battery, 3.3 V and 5 V conversion |
| 02_MCU | ESP32-S3-WROOM-1 module, boot/reset and native USB |
| 03_NFC | PN532, clock, matching network and NFC loop connector |
| 04_SUBGHZ | E07 CC1101 module and antenna selection |
| 05_GNSS_SD | MAX-M10S, GNSS antenna and microSD |
| 06_IR_UI | IR transmitter/receiver, RGB LEDs, buzzer and buttons |
| 07_SENSORS_IO | IMU, barometer, RTC, fuel gauge, I/O expander and headers |

KiCad 10 is installed locally. `PocketLab-Card.kicad_pro` is the project entry
point and the PCB scaffold contains the exact credit-card outline. Empty
functional sheet files are deliberate capture targets, not completed circuits.

## Required schematic checks

- USB-C CC resistors and native USB differential pair protection
- Correct ESP32 boot straps and antenna keep-out
- BQ24074 input/current/thermal programming and LiPo polarity
- Stable 3.3 V and 5 V converter compensation/layout per reference designs
- 5 V header current limiting and output discharge
- PN532 supply sequencing, clock and antenna tuning network
- Correct E07 module variant, castellated footprint and antenna keep-out
- GNSS 50 ohm feed, active antenna bias option and ESD
- microSD pull-ups and write-current decoupling
- Exposed GPIO series resistors and 3.3 V-only labeling

See `docs/assembly-strategy.md` before selecting or placing any footprint.

## PCB stack target

Four-layer, 1.6 mm FR-4:

1. L1: components, RF and short high-speed signals
2. L2: uninterrupted ground plane
3. L3: power planes and low-speed signals
4. L4: components and low-speed routing

The exact dielectric stack and RF trace widths must be recalculated against
the selected fabricator's stack-up before routing USB or 50 ohm RF traces.
