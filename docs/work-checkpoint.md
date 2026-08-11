# Work checkpoint — 2026-08-11

## Current inboard-antenna and three-IR checkpoint — 2026-08-11

- The active PCB and reproducible staging PCB now contain 252 footprints: 113
  front, 139 back and 220 physical nets; the placement file has no tracks.
- U3 is the 10 x 10 mm E07-900MM10S. Its pin-6 pi network reaches a T3-868M
  spring in an 18.8 x 6.58 mm open-bottom pocket. The pad follows after the
  required 0.6-mm PCB bridge; the complete spring stays inside the card envelope.
  The pad is the only electrical connection, while a marked nonconductive bond
  to the upper pocket wall mechanically secures the free end.
- D1-D3 are flat TSAL6200 emitters along the left short edge. All three bodies
  remain inside the outline and D3 clears the lower corner radius.
- J5 keeps all 30 connections and 2.54-mm pitch in a compact row-major 6 x 5
  matrix. Individual Dupont leads or breakaway strips fit; a 2 x 15 housing does not.
- ERC reports zero violations. Placement DRC has seven reviewed
  library-comparison warnings and 499 open connections; no copper-edge,
  silkscreen-edge or courtyard geometry violation remains.
- The firmware builds successfully with bounded authenticated NEC IR output;
  Sub-GHz TX and arbitrary GPIO output remain disabled.
- Routing is still the release blocker. This checkpoint is not order-ready.

## Compact-display checkpoint — 2026-08-10

- SW1 `RESET` and SW2 `BOOT` now use adjacent, front-side C&K KMR221GLFS
  service switches with explicit silkscreen labels. The larger SW3/SW4 user
  buttons remain unchanged for comfortable operation.
- LED1-LED4 now use compact 2-mm WS2812B-2020 packages with the existing 5-V
  logic-buffered chain and local C603-C606 decoupling.
- The protected LiPo connector J4 is on the back side and turned 90 degrees
  counter-clockwise relative to its former front-side orientation. Mirrored
  polarity marks are provided on the bottom silkscreen.
- Replaced the rejected 15.5 x 13 mm OLED carrier module with a bare
  EastRising ER-OLED0.42-1W panel (12 x 11 x 1.25 mm, 72 x 40 pixels).
- J8 now has the complete 16-way 0.65-mm FPC pinout and seven local 0805
  charge-pump/decoupling capacitors. The FPC is soldered before the glass is
  folded and bonded; it is not a plug-in module.
- Added SW5 as a low-current main switch on the TPS63070 enable path and
  exposed the freed GPIO38 through R606 on the separate 2.54-mm J9 pad.
- Generated design at that checkpoint: 250 symbols, 243 populated footprints, 175 named
  schematic nets. ERC is clean. The placement builder reports no unapproved
  component, edge, NFC, ESP antenna or Sub-GHz service-keepout collision.
- `PocketLab-Card.kicad_pcb` mirrors the new 243-footprint placement;
  `PocketLab-Card-planed.kicad_pcb` has regenerated L2 GND/L3 +3V3 planes.
- Routing is still open. The placement DRC has seven known footprint-library
  mismatch warnings and 499 expected unconnected items, so the project remains
  explicitly not order-ready.

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
