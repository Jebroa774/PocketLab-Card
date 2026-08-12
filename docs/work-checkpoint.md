# Work checkpoint — 2026-08-12

## Paused state — 2026-08-13

- Work was intentionally stopped at the user's request and all accepted local
  changes were saved before publishing the branch.
- The authoritative PCB now includes the first deterministic GND/+3V3
  plane-fanout pass: 730 outer-layer track segments and 214 through vias are
  present. Open connection items fell from 499 to 290. Twenty-one dense
  GND/+3V3 clusters remain explicitly reported by
  `hardware/scripts/route_plane_fanouts.py` for the next reviewed pass.
- LF RFID now shares the existing SPI SCK/MOSI/MISO bus instead of consuming
  three separately trapped ESP32 pins. U21 is the partial-power-down-safe
  SN74LV125ATPWR (LCSC C2675655); U22 is the LF_RFID_EN-controlled tri-state
  SN74LVC1G126DBVR (LCSC C7834). This prevents an unpowered LF domain from
  back-powering or driving the active SPI bus.
- The generated schematic/design netlist and PCB agree on that architecture;
  the final saved parity check passes and ERC reports 0 errors / 0 warnings.
  ESP32 pins 11/23/28 are intentionally NC; the SPI channel mapping was chosen
  so U21 can remain at its collision-free 0-degree placement.
- `route_lf_global.py` is saved as work in progress. Its latest atomic trial
  found legal routes for LF_RFID_EN and all three 5-V HTRC control signals,
  but the subsequent SPI_MOSI branch was blocked by those candidate paths.
  Because the pass is atomic, none of that unverified global LF copper was
  promoted to the authoritative PCB.
- The POWER netclass clearance is now 0.20 mm, matching the documented normal
  JLCPCB-capable design target and the existing fine-pitch package geometry.
  Wide 0.50/0.80-mm power-route requirements remain unchanged.
- This is a reproducible routing checkpoint, not an order-ready board.

## Saved state

- ESP32-S3-WROOM-1-N8R2 remains the V1 controller. ESP32-S31 was reviewed as a
  possible future V2 option but is not being introduced into this revision;
  changing to its larger, preliminary WROOM ecosystem would restart placement,
  routing and firmware validation without improving a current V1 requirement.
- Generated schematic: 273 symbols, 266 footprints and 180 named logical nets;
  the current PCB contains 231 physical nets, including three unique NC nets.
- GNSS hardware has been removed. U4 is now HTRC110 125-kHz LF RFID with
  switched 5 V, level translation, external 4-MHz clock and removable coil.
- ATECC608C-SSHDA-T, decoupling and the dedicated SW6 PAIR button are captured.
- U24/U25 add low-capacitance shunt protection to every exposed J5 I2C/SPI
  line. Direct GPIO and expander pins retain their existing series protection.
- TP601 and TP701-TP703 were removed: the last RGB output is intentionally NC.
  BMI270 retains both interrupt lines; BMP390 pin 7 is intentionally NC and
  pressure data remains available by I2C polling.
- R736/RT701 add a 10-kohm B3950 board-temperature divider on GPIO9 in the
  former 4 x 4 mm back-side pocket. J5 pin 7 is now probe-only through R714;
  eleven direct expansion GPIOs remain.
- Stale GNSS DNP rules were removed from the manufacturing exporter; its safety
  defaults now match the NFC, Sub-GHz and LF tuning footprints in this design.
- Repository cleanup removed the superseded placement render, empty capture-target
  sheets, generated PCB/autorouter intermediates and their duplicate DRC reports.
  These staging files are reproducible from `hardware/scripts` and are now ignored;
  the main schematic and `PocketLab-Card.kicad_pcb` remain authoritative.
- The placement builder fits all 266 footprints (131 front, 135 back) without
  unapproved courtyard, keepout or board-inset collision.
- The authoritative routed checkpoint contains 130 front and 136 back
  footprints. The one-part-per-side difference from the regenerated placement
  donor is limited to a generic unrouted packing slot; all 266 references exist.
- U4 and its LF resonance, current-limit, RX, oscillator and coil-interface
  parts now form one compact back-side analog island beside J3. C506/C507/C508
  are aligned as a straight tuning bank; C507/C508 remain DNP options.
- `LF_TX1`, `LF_TX2`, `LF_ANT_A`, `LF_ANT_B`, `LF_TAP`, `LF_RX`, `LF_CEXT`,
  `LF_QGND` and `LF_CLK_4M` are completely routed on B.Cu with no vias.
  The front-side U17 support island and its LF 5-V distribution to U4, Y501
  and C513 are also routed. A narrowly scoped U17 pin-escape rule permits a
  0.20-mm SOT-23 neckdown; three ordinary tented through-vias carry LF 5 V.
- The placement generator reserves the LF support route corridor so future
  regenerations cannot silently pack unrelated parts into it. The LF analog,
  placement-merge and support routes are reproducible with the three dedicated
  scripts in `hardware/scripts`.
- L2 GND and L3 +3V3 staging planes regenerate successfully.
- The PCB stack is now the nominal 1.2-mm, four-layer
  `JLC04121H-7628` target with 1-oz outer / 0.5-oz inner copper and ENIG.
  Confirm the live factory stack before freezing USB and RF widths.
- Routing has started. The main PCB contains the guarded digital fanout and
  DRC-clean local routes for U6_L1, U6_L2, U7_SW, RTC_OSCI and RTC_OSCO. U6
  input/output power, U7 input/output power, U7 feedback and the low-current
  5-V feedback sense branch are now also routed. The nearby IR branch was
  rerouted around Y701, and R405 now faces U3 -> antenna. CC2 and the provisional
  Sub-GHz feed are also complete. After replacing conflicting legacy copper
  with the reviewed LF routes, the board now contains 730 track segments and
  214 vias after the first GND/+3V3 plane-fanout pass.
- Two named B.Cu rule areas limit U7's unavoidable 0.20-mm power-pin neckdowns
  to the package exits and the reviewed Kelvin/sense corridor; the power rails
  widen to 0.50 mm outside those areas.
- R201/R202 are now vertical, side-by-side 0805 parts. The native USB pair is
  fully routed from U1 through both 22-ohm resistors and U16 to all four J1
  A6/B6/A7/B7 data pads. The MCU side is via-free; the connector bridge uses
  five 0.50/0.30-mm vias and a local 0.15-mm fine-pitch clearance area.
- U16 moved 0.55 mm inward and R102 is now a fixed front-side 0805 below the
  USB data crossover. J1 B5, R102, its local ground return and the U16 pin-6
  protection branch are routed. CC2 changes layer with two standard
  0.50/0.30-mm through vias and has no signal trace on L2/L3. The narrowly
  scoped 0.20-mm C103/C104 escape rule leaves every other power-pair clearance
  at 0.25 mm. R101 remains a fixed 0805 on the back beside the right edge.
- The Sub-GHz pi network is now routed at the provisional 0.36-mm width. C404
  is perpendicular to the feed, `/SUBGHZ_RF_MOD` stays on B.Cu and
  `/SUBGHZ_RF_ANT` makes exactly one 0.60/0.30-mm transition to F.Cu before the
  spring pocket. The front trace stays outside the antenna notch. `/OLED_VCC`
  was returned completely to the ratsnest because its old autorouter path ran
  through C404's corrected ground-shunt position.
- SW3/SW7/SW4 now form a compact, labeled UP/OK/DOWN row using the same
  KMR221GLFS footprint as RESET/BOOT. R607 is the SELECT pull-up; U9/P07 is the
  SELECT input and BMP390 INT is NC. PAIR remains a separate security button.
- SPI_SCK, SPI_MOSI, SPI_MISO, I2C_SCL, GPIO44_MCU, NFC_DVDD, the three user
  button nets, IR_LED_A1, IR_LED_K, GPIO43, NFC_LOADMOD, NFC_RESET_N,
  I2C_SDA, PAIR_N, SPI_MOSI_HDR, SPI_SCK_HDR, LF_DOUT_5V and OLED_VCC
  autorouter copper was removed as complete nets where it crossed the accepted
  USB/button/LF placement. These nets are intentionally back in the ratsnest,
  with no dangling copper stubs. This is why the total copper count fell while
  the routed LF block was added.
- The final saved KiCad checks pass schematic/PCB parity and ERC with 0 errors /
  0 warnings. DRC still reports 41 known non-release findings: 8 clearances,
  11 copper-to-edge findings, 16 embedded-thermal drill-size findings and six
  local footprint-library comparison warnings. There are 290 open connection
  items, so this remains only a routing checkpoint.
- Firmware remains at the preceding two-button checkpoint by explicit project
  priority; no firmware file was changed for the new SELECT hardware. That
  previous ESP32-S3 build provides LF power sequencing,
  HTRC110 configuration/phase/antenna diagnostics, ATECC presence detection,
  a physical 60-second pairing gate, web control, microSD, bounded NEC IR and
  board-temperature readout/80-degree-C shutdown with 70-degree-C hysteresis.
- Secure-element zone locking, persistent owner keys and the phone app are not
  implemented. No irreversible eFuses or ATECC locks have been applied.

## Next engineering steps

1. Confirm the live `JLC04121H-7628` data and recalculate the stack-dependent
   USB and provisional 0.36-mm Sub-GHz geometry. Retune the assembled pi
   network before treating the RF path as production-final.
2. Resume `route_lf_global.py` with negotiated/rip-up routing so the four LF
   control paths and the three shared-SPI branches coexist without crossings;
   then connect upstream `+5V_RAW`, LF_5V and the remaining reviewed grounds.
3. Finish the 21 reported plane clusters and the battery/USB/VSYS/5-V power
   trunks. Then reroute the deliberately cleared digital nets, including short
   U24/U25 clamp branches, refill planes and close all 290 ratsnest items.
4. Run full KiCad DRC, schematic/PCB parity, independent footprint review and
   JLCPCB DFM/BOM/CPL preview.
5. Assemble a small bring-up batch; current-limit first power-up and measure
   every rail before fitting the external coil.
6. Measure the real coil, choose C506/C507/C508, check HTRC phase/ANTFAIL,
   current, voltage and read range.
7. Keep firmware/app work deferred until the PCB routing and manufacturing
   package are complete; then update the input map for UP/OK/DOWN before any
   ATECC provisioning or locking work.

This checkpoint is not an order-ready fabrication release.
