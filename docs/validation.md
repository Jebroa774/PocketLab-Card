# Design validation log

## 2026-08-09 architecture baseline

- ESP32-S3-MINI-1 exposes 39 GPIOs in the selected N8 module configuration.
- 26 pins are allocated or deliberately reserved.
- 13 direct free GPIOs remain: 1, 2, 4, 8, 9, 37, 38, 39, 40, 41, 42, 47, 48.
- No duplicate ESP32 pin allocations were found.
- TCA9535 P10-P17 provide eight additional low-speed digital I/Os.
- J_EXT contains 30 positions at 2.54 mm pitch and its documented pin count balances.
- 433 MHz and 868 MHz CC1101 designs require different RF matching BOMs.
- 5 V auxiliary output is switchable and requires a 500 mA hardware current limit.

## Firmware scaffold

- Tool: PlatformIO Core 6.1.19
- Platform: Espressif 32
- Framework: Arduino-ESP32 3.3.8
- Target: ESP32-S3-DevKitC-1-N8, 8 MB flash, no PSRAM
- Result: successful clean build
- Initial size: 22,088 bytes RAM and 318,188 bytes flash

## Outstanding before PCB order

- Capture and run KiCad ERC on all schematic sheets.
- Select exact battery connector, protection and 5 V current limiter.
- Confirm every selected part against the assembly supplier's stock.
- Simulate/verify the IR pulse current and perform an optical safety review.
- Review regulator thermal behavior and switching-noise placement.
- Calculate USB and RF trace geometries from the fabricator's exact stack-up.
- Tune NFC, 868 MHz and GNSS antenna interfaces on assembled prototypes.
- Run KiCad DRC and independent schematic/layout review.
