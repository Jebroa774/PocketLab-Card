# Design validation log

## 2026-08-09 architecture baseline

- ESP32-S3-WROOM-1-N8R2 was selected for its 1.27 mm castellated edge pads,
  8 MB flash and 2 MB PSRAM.
- 12 direct free GPIOs remain: 1, 2, 4, 8, 9, 40, 41, 42, 43, 44, 47, 48.
- No duplicate ESP32 pin allocations were found.
- U9/TCA9535 P10-P17 provide eight additional low-speed digital I/Os through
  220-ohm series resistors; U18/TCA9534 handles the internal control outputs.
- J5 contains 30 positions at 2.54 mm pitch and its documented pin count balances.
- U3 is the 10 x 10 mm E07-900MM10S. Pin 6 feeds a DNP/0-ohm/DNP pi network and
  the T3-868M spring. The spring body, 18.8 x 6.58 mm pocket and adjacent pad
  remain inside the original card envelope. Only the right end is electrically
  connected; the marked left anchor is nonconductive and mechanical. Final
  tuning still requires S11 measurement with the received module, adhesive,
  enclosure and battery.
- 5 V auxiliary output is switchable and requires a 500 mA hardware current limit.

## 2026-08-09 assembly-oriented revision

- KiCad 10.0.3 installed locally; project and mechanical outline scaffolded.
- General passives are 0805; 0603 is allowed only where electrical/RF layout
  requires it. 0402, 0201, BGA and WLCSP packages are prohibited in V1.
- ESP32-S3-MINI was replaced with the larger ESP32-S3-WROOM-1 module.
- Bare CC1101 plus crystal/matching was replaced with an Ebyte castellated module.
- MIA-M10Q was replaced with the larger MAX-M10S LCC module.
- TCA9535 QFN was replaced with TCA9535PWR in TSSOP-24.
- RV-3028-C7 was replaced with PCF8563T in SOIC-8.
- BMI270 and BMP390 are optional because JLCPCB lists them as Standard-only.
- Top-only SMT was an early economy target. The current dense placement builder
  deliberately uses both PCB sides; final side allocation, assembler class and
  cost remain subject to DFM review. Headers and the 5 mm IR LED remain
  post-assembly hand-fit parts.

## Firmware checkpoint

- Tool: PlatformIO Core 6.1.19
- Platform: Espressif 32
- Framework: Arduino-ESP32 3.3.8
- Target: ESP32-S3-DevKitC-1-N8R2, 8 MB flash, 2 MB quad PSRAM
- Result after N8R2 pin remap: successful clean build
- Current full firmware image: 1,127,376-byte `firmware.bin` (2026-08-09 build)

## 2026-08-09 complete schematic checkpoint

- Tool: KiCad CLI 10.0.5
- Generated schematic: 259 symbols, 252 assigned footprints and 179 named logical nets.
- Current schematic ERC: 0 errors and 0 warnings.
- PN532 pin 39 DVDD is the internal-LDO output and directly feeds AVDD/TVDD;
  each supply has local decoupling. RX uses the implemented 2.7-kohm loop tap,
  1-nF AC coupling and 1-kohm VMID bias branch.
- AE1 is the project-local 35 x 27 mm, four-turn, 0.50/0.50 mm prototype loop.
  Its footprint reserves a 36 x 29 mm keep-out on all copper layers.
- GNSS V_BCKP is NC. The passive U.FL path is the default; R505/L501/C504 are
  DNP active-antenna bias options, and R507/R508 are fixed 1-kohm UART limits.
- microSD has C512 47-uF local bulk capacitance and U19/SRV05-4 signal ESD.
- J8 is the 12 x 11 mm ER-OLED0.42-1W bare panel. Its 16 FPC pads and all seven
  required 0805 support capacitors pass the generated pad and placement audit.
- J5 pins 28/30 and SJ1 implement the optional external 10-kohm battery NTC connection.
- Direct GPIOs, expander GPIOs and exposed I2C/SPI buses all have populated
  series-resistor stages. The one shared I2C pull-up pair is 3.3 kohm.
- TP105-TP110 expose VBUS_USB, VBUS_FUSED, VSYS, +3V3, +5V_RAW and +5V_AUX;
  TP101-TP104 expose the protected battery-chain nodes and GND.
- A clean ERC validates connectivity rules, not component suitability, RF
  behavior, layout, thermal performance or manufacturability.

## PCB status

- The earlier 21-footprint render was a mechanical placement study and is now
  superseded by the complete schematic/netlist.
- A fully netlisted placement/routing board is being generated and reviewed.
  Placement, critical-route design, plane strategy and DRC are not yet closed.
- No current PCB file is an order-ready fabrication release.

## Outstanding before PCB order

- Reconfirm every supplier part number, stock and PCBA class immediately before
  ordering; stock status is not a design-time guarantee.
- Reconfirm PN532 availability: NXP marks it NRND. A future controller migration
  may be required even though V1 retains PN532 for prototype compatibility.
- Simulate/verify the IR pulse current and perform an optical safety review.
- Review regulator thermal behavior and switching-noise placement.
- Calculate USB and RF trace geometries from the fabricator's exact stack-up.
- Finish placement and routing, then run KiCad DRC with zero unexplained items.
- Measure and tune the NFC loop/matching network on assembled prototypes with a
  VNA or NFC fixture; guessed values are not a production release.
- Verify GNSS insertion loss and Sub-GHz radiated behavior with the actual
  antennas and enclosure.
- Perform an independent schematic/layout, polarity, footprint and assembly
  review before generating an order archive.
- Verify RF frequency, power, duty cycle, antenna and emissions against the
  rules of every region in which the card will be operated. Prototype RF
  operation is not evidence of regulatory compliance.
