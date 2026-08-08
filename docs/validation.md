# Design validation log

## 2026-08-09 architecture baseline

- ESP32-S3-WROOM-1-N8R2 was selected for its 1.27 mm castellated edge pads,
  8 MB flash and 2 MB PSRAM.
- 12 direct free GPIOs remain: 1, 2, 4, 8, 9, 40, 41, 42, 43, 44, 47, 48.
- No duplicate ESP32 pin allocations were found.
- TCA9535 P10-P17 provide eight additional low-speed digital I/Os.
- J_EXT contains 30 positions at 2.54 mm pitch and its documented pin count balances.
- E07-900M10S and E07-400M10S share the selected footprint but are different
  populated radio variants and require the matching external antenna.
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
- All initial production SMT is constrained to the top side. Headers, 5 mm IR
  LED and optional radio module are hand-installed after PCBA.

## Firmware scaffold

- Tool: PlatformIO Core 6.1.19
- Platform: Espressif 32
- Framework: Arduino-ESP32 3.3.8
- Target: ESP32-S3-DevKitC-1-N8R2, 8 MB flash, 2 MB quad PSRAM
- Result after N8R2 pin remap: successful clean build
- Current scaffold size: 22,172 bytes RAM and 321,570 bytes flash

## KiCad scaffold checks

- Tool: KiCad CLI 10.0.5
- Root schematic loads all seven linked hierarchical sheet files.
- Scaffold ERC: 0 errors and 0 warnings.
- Credit-card Edge.Cuts outline DRC: 0 errors, 0 warnings and 0 open items.
- These results prove that the hierarchy and mechanical files are valid and
  that the outline closes. Functional sheets are still capture targets, so
  the results do not validate any electrical circuit yet.

## Outstanding before PCB order

- Capture and run KiCad ERC on all functional schematic sheets.
- Select exact battery connector, protection and 5 V current limiter.
- Reconfirm every supplier part number, stock and PCBA class immediately before
  ordering; stock status is not a design-time guarantee.
- Simulate/verify the IR pulse current and perform an optical safety review.
- Review regulator thermal behavior and switching-noise placement.
- Calculate USB and RF trace geometries from the fabricator's exact stack-up.
- Tune NFC, 868 MHz and GNSS antenna interfaces on assembled prototypes.
- Run KiCad DRC and independent schematic/layout review.
