# PocketLab Card V1

PocketLab Card V1 is a credit-card-outline, battery-capable ESP32-S3 field
tool. The design is original and does not copy SGP branding, artwork, PCB
layout, or firmware.

## V1 feature set

- ESP32-S3 Wi-Fi/BLE controller with local web interface
- PN532 13.56 MHz NFC reader/writer
- CC1101 Sub-GHz transceiver, initially optimized for the European 868 MHz band
- u-blox MIA-M10Q GNSS receiver with external antenna connector
- microSD trip and capture storage
- high-power 940 nm IR transmitter and 38 kHz IR receiver
- USB-C data/power, external 1-cell LiPo connector, charging and power path
- regulated 3.3 V rail and switchable 5 V auxiliary/IR rail
- 6-axis IMU, barometer, RTC and battery fuel gauge
- RGB LEDs, buzzer and user buttons
- 2.54 mm expansion headers

## Target mechanics

- Board outline: 85.60 mm x 53.98 mm, rounded corners
- PCB: 4 layers, 1.6 mm FR-4
- Components on both sides where RF keep-outs allow
- Unpopulated 2 x 15, 2.54 mm expansion footprint
- Initial prototype quantity: 5 assembled boards

## Repository layout

```text
PocketLab-Card/
|-- docs/           Architecture, pin allocation and design constraints
|-- hardware/       KiCad design source and preliminary BOM
|-- firmware/       ESP32 board definition and firmware source
`-- manufacturing/  Fabrication and assembly outputs
```

## Current status

The system architecture, first-pass pin allocation, expansion header and
power domains are frozen for schematic capture. KiCad is not currently
installed in the local environment, so the checked design tables are the
source of truth until the schematic can be captured and validated with ERC.

All RF transmit functions are intended only for frequencies, devices and
systems the operator is permitted to use.
