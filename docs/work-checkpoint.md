# Work checkpoint — 2026-08-09

## Pause checkpoint — 2026-08-10

Work was paused at the user's request after the placement-source audit. The
reproducible source scripts are ahead of the tracked generated PCB artifacts;
regenerate the schematic, netlisted board and plane board before resuming
routing. Do not treat the current PCB files as order-ready.

Saved source state:

- Generator still produces 241 symbols, 234 populated footprints, 168 named
  nets and 38 intentional no-connect nets; a fresh KiCad ERC reports 0 items.
- The latest temporary builder run passes pad/net parity, four-layer stackup,
  board-inset, full NFC reservation and ESP antenna-placement assertions.
- Latest temporary placement DRC has no copper-clearance or courtyard errors;
  only 499 expected unrouted items and 60 silkscreen/text warnings remain.
- U1 now uses the project-local physical-body courtyard while retaining the
  complete stock 48 x 21 mm all-copper-layer antenna rule area.
- The USB/charger, 3V3 buck-boost, 5V boost, battery protection and IR-current
  islands have been electrically repacked. R710-R734 all have deterministic,
  collision-free positions around U1, U9 and the 2.54-mm J5 header.
- Dense reference designators are now kept on Fab/assembly layers rather than
  production silkscreen. The guarded plane and FreeRouting scripts include the
  inner-plane and critical-net/via checks completed in this session.

Open items deliberately left for the next session:

1. Finish the Sub-GHz I-PEX mechanical audit. The provisional MHF-I mating-tool
   clearance is a 9.5-mm diameter around approximately `(80.8, 55.3)` on the
   back side. At minimum C116, R109, R111, R112 and R122 must be moved out of
   that space and the keepout must be encoded in the builder/board guide.
2. Finish the RGB/IR receiver audit. WS2812B-MINI-V3 is not guaranteed from a
   3.3-V supply (published minimum is 3.7 V); decide and implement the paused
   +5V_RAW/TTL-buffer solution, then place LED1-LED4 with local C603-C606.
3. Finish the paused U15/AUX5 repack for shorter R123 ILIM and R127 EN paths.
4. Regenerate the tracked schematic/design JSON, netlisted board, L2/L3 plane
   board and matching project/rule copies; rerun ERC/DRC before autorouting.
5. Resume guarded routing only after the three placement items above are
   closed. USB, GNSS RF, NFC, clocks, switch nodes and power remain manual.

This checkpoint intentionally stops before autorouting. The tracked main PCB
now mirrors the validated placement staging board so opening
`hardware/PocketLab-Card.kicad_pro` shows the real hardware rather than the old
21-footprint mechanical study.

## Saved state

- Schematic: 241 symbols, 234 assigned footprints and 168 named nets.
- KiCad ERC: 0 violations.
- Placement: 234 footprints (112 front, 122 back), 0 tracks and 0 zones.
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
