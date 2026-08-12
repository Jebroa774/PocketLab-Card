# Mechanical placement budget

The rounded 85.60 x 53.98 mm outline provides approximately 4,612 mm2 of PCB
area. This is enough for the selected architecture, but it requires a dense
two-sided placement rather than a mostly empty development board.

## Planning envelopes

| Zone | Working envelope | Placement intent |
|---|---:|---|
| ESP32-S3-WROOM body / embedded antenna keep-out | 19 x 26 mm / 48 x 21 mm | Short edge; most of the antenna keep-out extends outside the PCB, while its board-intersecting part stays empty on both sides |
| E07-900MM10S and antenna match | 10 x 10 mm module plus three 0805 matching sites | Back side beside the lower-edge spring feed |
| T3-868M spring pocket | 18.8 x 6.58 mm recess plus adjacent solder pad | Complete spring stays inside the original card envelope |
| HTRC110, protected tuning network and coil connector | 20 x 15 mm | Short resonant loop away from switch nodes |
| NFC loop and tuning reservation | 36 x 29 mm | 35 x 27 mm four-turn copper loop; full all-layer keep-out |
| microSD and card insertion path | 17 x 15 mm | Edge-accessible |
| Bare OLED glass / final folded envelope | 12 x 11 mm | Front side; direct 16-way FPC plus adjacent 0805 charge-pump bank |
| USB, charger, 3.3 V and 5 V power | 30 x 22 mm | Compact power island with thermal copper |
| 6 x 5 expansion matrix | 15 x 12.5 mm | Thirty 2.54-mm through holes; individual Dupont leads or breakaway strips |
| Three flat IR emitters, RGB, buttons, RTC and optional sensors | 25 x 19 mm | Distributed in remaining pockets |

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

## Audited residual space

The 262-footprint checkpoint was sampled on a 0.25-mm grid; the current
266-footprint estimate also accounts for the compact SELECT switch/R607 and
the expanded R736/RT701 courtyards. The conservative audit includes a
0.20-mm margin around courtyards, opposite-side through-hole projections and
the full NFC, ESP32 and Sub-GHz reservations.

| Side | Fragmented free grid area | Largest square pocket | Largest useful-looking strips |
|---|---:|---:|---|
| Front | about 478 mm2 | 2.5 x 2.5 mm | 7.75 x 2.5 mm and 8.0 x 2.0 mm |
| Back | about 568 mm2 | about 3.0 x 3.0 mm | 3.0 x 6.75 mm and 6.75 x 2.75 mm |

The former 4.0 x 4.0 mm back pocket now contains the R736/RT701 temperature
divider. The summed area is not a component budget: most of it consists of narrow gaps
between pads and courtyards. The four removed pads release about 16.8 mm2 of
actual courtyard area (roughly 24 mm2 when the audit margin is included), but
they do not create one large contiguous module site. Reserve these pockets for
routing, return paths and later reviewed GND stitching.

## Height

- Bare board: 1.2 mm.
- ESP32-S3-WROOM module: approximately 3.1 mm above its mounting surface.
- Bare OLED: approximately 1.25 mm panel thickness; no carrier PCB or pin header.
- E07-900MM10S module: verify its received maximum height and solder fillets;
  the current layout uses its 10 x 10 mm castellated body on the back.
- The E07 module and microSD socket are on the opposite side, while the JST
  battery connector can exceed the ESP32 height. The complete unheadered card
  therefore needs a provisional 8-9 mm overall envelope before enclosure
  clearance; confirm it in the final 3D model and against received parts.
- The three 5 mm THT IR LEDs lie flat and remain inboard. They still set a
  local height of roughly 5 mm above the front surface and require hand forming.

The design is credit-card-shaped, not ISO wallet-card-thin. Keeping the battery
external avoids adding several millimetres across the whole board.
