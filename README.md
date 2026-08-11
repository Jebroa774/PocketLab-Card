# PocketLab Card V1

PocketLab Card V1 is a credit-card-outline, battery-capable ESP32-S3 field
tool. The design is original and does not copy SGP branding, artwork, PCB
layout, or firmware.

## V1 feature set

- ESP32-S3-WROOM-1-N8R2 Wi-Fi/BLE module with local web interface
- PN532 13.56 MHz NFC reader/writer
- Ebyte E07-900MM10S CC1101 Sub-GHz module with an inboard 868 MHz spring antenna
- HTRC110-based 125 kHz LF-RFID front end with removable/tuneable coil
- ATECC608C secure element and a dedicated physical app-pairing button
- microSD capture and app-data storage
- three high-power 940 nm IR emitters and a 38 kHz IR receiver
- USB-C data/power, external 1-cell LiPo connector, charging and power path
- regulated 3.3 V rail and switchable 5 V auxiliary/IR rail
- optional 6-axis IMU/barometer, SOIC RTC and battery fuel gauge
- four RGB LEDs, three UP/OK/DOWN user buttons and a bare 0.42-inch 72 x 40 OLED
- 2.54 mm expansion headers

## Target mechanics

- Board outline: 85.60 mm x 53.98 mm, rounded corners
- PCB: 4 layers, 1.2 mm FR-4
- Unpopulated compact 6 x 5 matrix of 30 holes on 2.54 mm pitch
- Three flat, edge-facing IR emitters and an inboard spring-antenna pocket
- Initial prototype quantity: 5 assembled boards

The PCB keeps the credit-card outline, but it is not a wallet-thickness card.
Because the dense layout places modules/connectors on both sides, the complete
unheadered assembly is expected to need roughly 8-9 mm of thickness before
enclosure clearance; the final value must be checked in the KiCad 3D model and
against received parts. The three 5 mm IR emitters are installed flat by hand;
their lenses and the complete spring antenna remain inside the original card
envelope, although both features still require enclosure openings.

![Current routing checkpoint](docs/design-overview/card-top.png)

## Repository layout

```text
PocketLab-Card/
|-- docs/           Architecture, pin allocation and design constraints
|-- hardware/       KiCad design source and preliminary BOM
|-- firmware/       ESP32 board definition and firmware source
`-- manufacturing/  Fabrication and assembly outputs
```

## Current status

The generated KiCad 10 schematic now contains 273 symbols, 266 assigned
footprints and 183 named logical nets (231 physical PCB nets). Its current ERC
report is clean. This includes
the two I/O expanders, protected expansion connections, LF RFID, the secure
element, the physical PAIR button, three-button OLED navigation, microSD,
board-temperature monitor, rail test points, the 5-V RGB level shifter, the direct-soldered
12 x 11 mm OLED, and the project-local 35 x 27 mm four-turn NFC-loop footprint.

PCB placement is mechanically audited and routing has started. The image above
is the current routing checkpoint and uses approximate preview models for the
hand-fitted IR and spring-antenna parts. The project is **not
ready to order** until routing,
stack-up-dependent USB/RF/LF geometry, DRC, manufacturing exports and independent
review are complete. The NFC loop is a prototype geometry whose matching must
be measured and tuned on the assembled card with a VNA; PN532 is NRND and its
availability must be checked before every build.

All RF transmit functions are intended only for frequencies, power levels,
antennas, duty cycles, devices and systems the operator is permitted to use.
Prototype RF performance and regulatory compliance have not yet been verified.
