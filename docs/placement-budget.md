# Mechanical placement budget

The rounded 85.60 x 53.98 mm outline provides approximately 4,612 mm2 of PCB
area. This is enough for the selected architecture, but it requires a dense
two-sided placement rather than a mostly empty development board.

## Planning envelopes

| Zone | Working envelope | Placement intent |
|---|---:|---|
| ESP32-S3-WROOM body / embedded antenna keep-out | 19 x 26 mm / 48 x 21 mm | Short edge; most of the antenna keep-out extends outside the PCB, while its board-intersecting part stays empty on both sides |
| E07-900M10S IPEX module and access | 24 x 18 mm | Separate edge; integrated IPEX kept accessible |
| MAX-M10S, antenna bias and U.FL | 20 x 15 mm | Quiet corner away from switchers |
| NFC loop and tuning reservation | 36 x 29 mm | 35 x 27 mm four-turn copper loop; full all-layer keep-out |
| microSD and card insertion path | 17 x 15 mm | Edge-accessible |
| USB, charger, 3.3 V and 5 V power | 30 x 22 mm | Compact power island with thermal copper |
| 2 x 15 expansion header | 40 x 7 mm | Through-hole strip, top or bottom header installation |
| IR, RGB, buttons, RTC and optional sensors | 25 x 15 mm | Distributed in remaining pockets |

The NFC footprint itself enforces a 36 x 29 mm keep-out against foreign tracks,
vias, pads, pours and footprints on all copper layers, with only local relief
for its own terminals/crossover. Other planning envelopes may overlap during
floorplanning, but the final placement must not violate that keep-out. No
additional large module should be promised until the actual netlisted placement
and routing pass DRC; the remaining apparent area is routing and return-path
reserve, not guaranteed expansion space.

The loop's four turns, 0.50 mm track width and 0.50 mm spacing are a prototype
starting point. Battery, enclosure, hand proximity, stack-up and nearby metal
alter inductance and Q, so the final PN532 matching requires assembled-board
VNA measurement.

## Height

- Bare board: 1.6 mm.
- ESP32-S3-WROOM module: approximately 3.1 mm above its mounting surface.
- The E07 module and microSD socket are on the opposite side, while the JST
  battery connector can exceed the ESP32 height. The complete unheadered card
  therefore needs a provisional 8-9 mm overall envelope before enclosure
  clearance; confirm it in the final 3D model and against received parts.
- The optional 5 mm THT IR LED is edge-facing and does not define the flat
  board thickness, but it protrudes beyond the outline.

The design is credit-card-shaped, not ISO wallet-card-thin. Keeping the battery
external avoids adding several millimetres across the whole board.
