# Hardware design source

## Functional blocks

| Logical block | Contents |
|---|---|
| 00_ROOT | Power domains, buses and hierarchical connections |
| 01_USB_POWER | USB-C, ESD, charger, battery, 3.3 V and 5 V conversion |
| 02_MCU | ESP32-S3-WROOM-1 module, boot/reset and native USB |
| 03_NFC | PN532, clock, matching/RX networks and four-turn PCB loop |
| 04_SUBGHZ | E07-900M10S IPEX CC1101 module; pin 21 NC |
| 05_GNSS_SD | MAX-M10S, GNSS antenna and microSD |
| 06_IR_UI | IR transmitter/receiver, RGB LEDs, buzzer and buttons |
| 07_SENSORS_IO | IMU, barometer, RTC, fuel gauge, U9/U18 and headers |

KiCad 10 is installed locally. `PocketLab-Card.kicad_pro` is the project entry
point and the PCB scaffold contains the exact credit-card outline. The current
generated schematic comprises 241 symbols, 234 assigned footprints and 168
named nets; `erc-current.rpt` reports zero errors and zero warnings.

The schematic and its machine-readable net description are reproducible with
KiCad's bundled Python:

```powershell
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/generate_schematic.py PocketLab-Card.kicad_sch --design-json design-netlist.json
```

The project-local footprint library includes the manufacturer-derived special
packages and `NFC_Loop_35x27mm_4T_TUNE`. The latter is a four-turn, 0.50/0.50
mm preliminary loop with a 35 x 27 mm copper envelope and a full 36 x 29 mm
all-copper-layer keep-out. Its matching is intentionally not a release value:
measure and tune the populated prototype with the final stack-up, enclosure and
battery using a VNA or suitable NFC fixture.

`PocketLab-Card-netlisted.kicad_pcb` is the reproducible placement work file.
The tracked `PocketLab-Card.kicad_pcb` currently mirrors that saved placement
checkpoint so the normal project opens all 234 footprints. Routing and DRC are
still being developed; neither file is an order-ready fabrication release.

## Required layout, sourcing and bring-up checks

- USB-C CC resistors and native USB differential pair protection
- Correct ESP32 boot straps and antenna keep-out
- BQ24074 input/current/thermal programming and LiPo polarity
- Stable 3.3 V and 5 V converter compensation/layout per reference designs
- 5 V header current limiting and output discharge
- PN532 DVDD-derived AVDD/TVDD supplies, RX network and measured antenna tuning
- E07-900M10S IPEX variant, with pin 21 NC and no second board-level RF connector
- GNSS 50 ohm feed, passive U.FL default and DNP active-antenna bias option
- microSD pull-ups, 47 uF write-transient bulk capacitance and U19 ESD array
- 100 ohm series protection on 12 direct GPIOs and the exposed I2C/SPI buses
- 220 ohm series protection on all eight expander GPIOs
- optional J7 external 10-kohm NTC input, selected by cutting SJ1
- VBUS_USB, VBUS_FUSED, VSYS, +3V3, +5V_RAW and +5V_AUX test points

See `docs/assembly-strategy.md` before selecting or placing any footprint.

## PCB stack target

Four-layer, nominal 1.6 mm FR-4, encoded for the JLC04161H-7628 target:

1. L1: components, RF and short high-speed signals
2. L2: uninterrupted ground plane
3. L3: power plane only
4. L4: components and low-speed routing

The encoded build uses 35-um outer copper, 15.2-um inner copper, two 0.2104-mm
7628 prepregs and a 1.065-mm core. The 0.36-mm GNSS feed is provisional: the
final 50-ohm grounded-coplanar geometry must be recalculated and confirmed
against the exact stack-up accepted in the order before fabrication.
