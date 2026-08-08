# Mechanical placement budget

The rounded 85.60 x 53.98 mm outline provides approximately 4,612 mm2 of PCB
area. This is enough for the selected architecture, but it is a dense top-side
layout rather than a mostly empty development board.

## Planning envelopes

| Zone | Working envelope | Placement intent |
|---|---:|---|
| ESP32-S3-WROOM plus antenna keep-out | 26 x 22 mm | Short edge, all-layer antenna keep-out |
| E07 Sub-GHz module and access | 24 x 18 mm | Separate edge, U.FL/feed kept short |
| MAX-M10S, antenna bias and U.FL | 20 x 15 mm | Quiet corner away from switchers |
| NFC loop and tuning reservation | 42 x 30 mm | Copper keep-out dominates; some non-metal loads may overlap internally |
| microSD and card insertion path | 17 x 15 mm | Edge-accessible |
| USB, charger, 3.3 V and 5 V power | 30 x 22 mm | Compact power island with thermal copper |
| 2 x 15 expansion header | 40 x 7 mm | Through-hole strip, top or bottom header installation |
| IR, RGB, buttons, RTC and optional sensors | 25 x 15 mm | Distributed in remaining pockets |

The envelopes intentionally include service and routing clearance and therefore
overlap in places, especially inside the NFC loop. A realistic routing reserve
is about 10-15 percent after the first placement pass. No additional large
module should be promised until the actual footprints and RF keep-outs are on
the PCB; small I2C sensors, test pads and unpopulated solder jumpers can still
fit.

## Height

- Bare board: 1.6 mm.
- ESP32-S3-WROOM module: approximately 3.1 mm above the mounting surface.
- Expected assembled thickness at that point: approximately 4.7 mm before
  solder, tolerance and enclosure clearance.
- The optional 5 mm THT IR LED is edge-facing and does not define the flat
  board thickness, but it protrudes beyond the outline.

The design is credit-card-shaped, not ISO wallet-card-thin. Keeping the battery
external avoids adding several millimetres across the whole board.
