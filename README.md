# PocketLab Card V1

PocketLab Card V1 is a credit-card-outline, battery-capable ESP32-S3 field
tool. The design is original and does not copy SGP branding, artwork, PCB
layout, or firmware.

## V1 feature set

- ESP32-S3-WROOM-1-N8R2 Wi-Fi/BLE module with local web interface
- PN532 13.56 MHz NFC reader/writer
- Ebyte CC1101 Sub-GHz module, initially the European 868 MHz variant
- u-blox MAX-M10S GNSS receiver with external antenna connector
- microSD trip and capture storage
- high-power 940 nm IR transmitter and 38 kHz IR receiver
- USB-C data/power, external 1-cell LiPo connector, charging and power path
- regulated 3.3 V rail and switchable 5 V auxiliary/IR rail
- optional 6-axis IMU/barometer, SOIC RTC and battery fuel gauge
- RGB LEDs, buzzer and user buttons
- 2.54 mm expansion headers

## Target mechanics

- Board outline: 85.60 mm x 53.98 mm, rounded corners
- PCB: 4 layers, 1.6 mm FR-4
- All production SMT on the top side for the initial economical assembly
- Unpopulated 2 x 15, 2.54 mm expansion footprint
- Initial prototype quantity: 5 assembled boards

The PCB keeps the credit-card outline, but it is not a wallet-thickness card:
the 1.6 mm PCB plus the ESP32 module is about 4.7 mm before solder and
mechanical tolerances. The optional edge-facing 5 mm IR LED protrudes beyond
the outline and is installed by hand after assembly.

![Top-side placement draft](docs/placement-top.png)

## Repository layout

```text
PocketLab-Card/
|-- docs/           Architecture, pin allocation and design constraints
|-- hardware/       KiCad design source and preliminary BOM
|-- firmware/       ESP32 board definition and firmware source
`-- manufacturing/  Fabrication and assembly outputs
```

## Current status

KiCad 10 is installed and the first placement draft contains 21 real
footprints on the exact card outline. The placement is deliberately unrouted;
the functional schematic, custom footprints, passives and copper still have to
be completed. The design is not ready to order until schematic ERC, PCB DRC and
the checks in `docs/validation.md` pass.

All RF transmit functions are intended only for frequencies, devices and
systems the operator is permitted to use.
