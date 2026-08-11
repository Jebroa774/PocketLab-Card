# Work checkpoint — 2026-08-11

## Saved state

- Generated schematic: 273 symbols, 266 footprints, 183 named logical nets
  and 231 physical PCB nets; ERC is 0 errors / 0 warnings.
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
- The placement builder fits all 266 footprints (132 front, 134 back) without
  unapproved courtyard, keepout or board-inset collision.
- The routed checkpoint retains 128 front and 138 back footprints from its
  validated staging allocation. The builder/checkpoint side-count difference
  consists only of generic unrouted packing slots; all 266 references exist.
- LF resonance/current-limit/RX parts are fixed around U4/J3 rather than left
  to the generic auto-packer.
- L2 GND and L3 +3V3 staging planes regenerate successfully.
- The PCB stack is now the nominal 1.2-mm, four-layer
  `JLC04121H-7628` target with 1-oz outer / 0.5-oz inner copper and ENIG.
  Confirm the live factory stack before freezing USB and RF widths.
- Routing has started. The main PCB contains the guarded digital fanout and
  DRC-clean local routes for U6_L1, U6_L2, U7_SW, RTC_OSCI and RTC_OSCO. U6
  input/output power, U7 input/output power, U7 feedback and the low-current
  5-V feedback sense branch are now also routed. The nearby IR branch was
  rerouted around Y701, and R405 now faces U3 -> antenna. CC2 and the provisional
  Sub-GHz feed are also complete. The board currently contains 498 track
  segments and 29 vias.
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
  button nets, IR_LED_A1, GPIO43, NFC_LOADMOD, LF_DOUT_5V and OLED_VCC
  autorouter copper was removed as complete nets where it crossed the accepted
  USB/button placement. These nets are intentionally back in the ratsnest,
  with no dangling copper stubs.
- KiCad DRC has no routed-geometry or schematic-parity error. Six reviewed
  local footprint-library comparison warnings remain and 499 connection items
  are still open, so this is only a routing checkpoint.
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
2. Resolve the LF placement/rule mismatch before routing: several sensitive LF
   nets currently join front- and back-side SMD pads although the present rule
   forbids vias. Re-place those parts on one side or explicitly review a small
   controlled transition set; then route LF resonant/RX and NFC manually.
3. Complete the remaining digital nets, including short U24/U25 clamp branches; then
   add reviewed GND stitching, refill planes and close all 499 ratsnest items.
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
