# Hardware design source

## Planned KiCad sheets

| Sheet | Contents |
|---|---|
| 00_ROOT | Power domains, buses and hierarchical connections |
| 01_USB_POWER | USB-C, ESD, charger, battery, 3.3 V and 5 V conversion |
| 02_MCU | ESP32-S3 module, boot/reset, USB and debug |
| 03_NFC | PN532, clock, matching network and NFC loop connector |
| 04_SUBGHZ | CC1101, 26 MHz clock, matching network and antenna selection |
| 05_GNSS_SD | MIA-M10Q, GNSS antenna and microSD |
| 06_IR_UI | IR transmitter/receiver, RGB LEDs, buzzer and buttons |
| 07_SENSORS_IO | IMU, barometer, RTC, fuel gauge, I/O expander and headers |

The local machine currently has no KiCad executable. Schematic capture should
start from the checked pin table and preliminary BOM after KiCad is installed.
Do not hand-edit an unvalidated `.kicad_sch` file as a substitute for ERC.

## Required schematic checks

- USB-C CC resistors and native USB differential pair protection
- Correct ESP32 boot straps and antenna keep-out
- BQ24074 input/current/thermal programming and LiPo polarity
- Stable 3.3 V and 5 V converter compensation/layout per reference designs
- 5 V header current limiting and output discharge
- PN532 supply sequencing, clock and antenna tuning network
- CC1101 band-specific reference matching network
- GNSS 50 ohm feed, active antenna bias option and ESD
- microSD pull-ups and write-current decoupling
- Exposed GPIO series resistors and 3.3 V-only labeling

## PCB stack target

Four-layer, 1.6 mm FR-4:

1. L1: components, RF and short high-speed signals
2. L2: uninterrupted ground plane
3. L3: power planes and low-speed signals
4. L4: components and low-speed routing

The exact dielectric stack and RF trace widths must be recalculated against
the selected fabricator's stack-up before routing USB or 50 ohm RF traces.
