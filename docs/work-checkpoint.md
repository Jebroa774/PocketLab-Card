# Work checkpoint — 2026-08-09

This checkpoint intentionally stops before autorouting. The tracked main PCB
now mirrors the validated placement staging board so opening
`hardware/PocketLab-Card.kicad_pro` shows the real hardware rather than the old
21-footprint mechanical study.

## Saved state

- Schematic: 239 symbols, 232 assigned footprints and 168 named nets.
- KiCad ERC: 0 violations.
- Placement: 232 footprints (107 front, 125 back), 0 tracks and 0 zones.
- Board: 85.60 x 53.98 mm, four layers, nominal 1.6 mm.
- Encoded stack target: JLC04161H-7628, 35-um outer / 15.2-um inner copper,
  0.2104-mm 7628 prepregs, 1.065-mm core and ENIG.
- The complete AE1 NFC reservation and the board-intersecting ESP32 antenna
  keepout are empty on both sides.
- Placement audit found no shorts, forbidden-item/antenna-keepout violations,
  or through-hole/thermal-via projection through an opposite-side component.
- Firmware builds successfully. GNSS UART now stays high-impedance while
  `GNSS_3V3` is off and is disconnected before power-off.

Primary files:

- `hardware/PocketLab-Card.kicad_pcb`: saved placement checkpoint opened by the
  normal KiCad project.
- `hardware/PocketLab-Card-netlisted.kicad_pcb`: reproducible placement staging
  copy produced by `hardware/scripts/build_pcb.py`.
- `hardware/PocketLab-Card.kicad_dru`: custom power, USB, GNSS, NFC and crystal
  rules.
- `hardware/scripts/add_planes.py`: tested staging step for filled L2 GND and
  L3 +3V3 planes; it has not yet been applied to the final saved placement.
- `hardware/scripts/route_pcb.py`: guarded DSN/FreeRouting/SES workflow; no
  final SES or routed board has been produced yet.

## Known DRC work at the checkpoint

The board is deliberately un-routed and **not order-ready**. The saved DRC run
reported:

- 499 unconnected ratsnest items;
- 48 footprint-internal clearance errors caused by fine-pitch manufacturer
  land patterns versus the generic 0.20/0.25-mm board rules;
- 16 0.20-mm thermal-via drills versus the generic 0.30-mm board minimum;
- two conservative U1 courtyard overlaps and two intentional J4 mounting-pad
  edge-clearance errors;
- 503 silkscreen/text warnings that need cleanup after routing;
- 264 schematic-parity warnings, mainly KiCad's `/NET` hierarchical names
  versus the generated board's `NET` names plus footprint-field differences.

No exception should be added broadly. Resolve or scope each footprint-local,
edge and parity rule before a fabrication export.

## Resume sequence

1. Resolve/scope the 68 placement DRC errors and the schematic-parity mapping;
   rerun DRC with the basename-matched `.kicad_pro` and `.kicad_dru`.
2. Generate `PocketLab-Card-planed.kicad_pcb` with `add_planes.py`; verify both
   antenna keepouts remain free of plane copper.
3. Run the guarded FreeRouting workflow for noncritical signals only. Fanout is
   disabled and L2/L3 are non-routable power layers.
4. Manually route/review USB, GNSS RF, NFC matching, converter switch nodes and
   all power paths; then add/review outer GND pours and stitching vias.
5. Reach zero DRC errors and zero unconnected items, clean silkscreen/parity,
   run the manufacturing release checks and complete procurement metadata.
6. Before ordering, independently review polarity/orientation, LiPo safety,
   JLCPCB DFM/CPL, controlled impedance and all RF/regulatory assumptions.
   Tune the fabricated NFC loop with a VNA; its current values are prototypes.
