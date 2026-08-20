# Design validation log

## Architecture checks

- ESP32-S3-WROOM-1-N8R2; no duplicate dedicated GPIO allocations.
- Eleven direct J5 GPIOs remain: 1, 2, 4, 8, 40, 41, 42, 43, 44, 47, 48.
- GPIO9 is reserved for the internal board NTC; J5 pin 7 is a protected
  high-impedance measurement point, not a general-purpose output.
- GPIO38 is dedicated to active-low PAIR. U9 adds eight low-speed EX inputs;
  U18 controls charger, AUX 5 V, NFC reset, LF 5 V and the 5-V boost.
- J5 contains 30 plated positions at 2.54-mm pitch.
- LF serial logic is translated in both directions; HTRC110 and its clock use
  switched 5 V, while the ESP32 and ATECC608C remain on 3.3 V.
- ATECC608C is present in SOIC-8 but intentionally unprovisioned.

## 2026-08-17 generated design

- KiCad 10 schematic: 274 symbols, 267 footprints, 181 logical/231 PCB nets.
- ERC: 0 errors, 0 warnings.
- Placement builder: 131 front and 136 back footprints; scripted courtyard, board,
  NFC, ESP and spring-pocket keepout audit passes.
- The authoritative routed checkpoint contains 130 front and 137 back
  footprints. Its one-part-per-side difference from the regenerated donor is
  limited to a generic unrouted packing slot; all 267 references remain present.
- Inner-plane staging regenerates with L2 GND and L3 +3V3 plus switcher cutouts.
- Stack-up audit: nominal 1.2-mm `JLC04121H-7628`, four copper layers,
  0.665-mm core, two 0.2104-mm 7628 prepregs and ENIG are serialized in the
  template and authoritative main board. The placement builder repeats this
  audit whenever the untracked staging boards are regenerated.
- Routing checkpoint: guarded digital fanout plus DRC-clean U6_L1, U6_L2,
  U7_SW, RTC_OSCI/RTC_OSCO, U6/U7 local power and U7 feedback routes. The two
  U7 power-pin neckdowns and the 5-V Kelvin branch are confined by named rule
  areas. R405 orientation was corrected before RF routing. The provisional
  Sub-GHz feed is now retained DRC-clean: C404 is perpendicular to the line,
  the module-side section stays on B.Cu, and one 0.60/0.30-mm via moves the
  antenna-side section to F.Cu outside the spring-notch edge clearance.
- The HTRC110 analog island is now coherent on B.Cu. All nine sensitive LF
  nets (`LF_TX1`, `LF_TX2`, `LF_ANT_A`, `LF_ANT_B`, `LF_TAP`, `LF_RX`,
  `LF_CEXT`, `LF_QGND`, `LF_CLK_4M`) are completely routed without a via.
  The straight C506/C507/C508 tuning bank preserves two DNP tuning sites.
- U17 and the LF support parts form a separate front-side island. The local
  `LF_5V` route to U4, Y501 and C513 uses three standard tented vias and a
  named, package-local 0.20-mm SOT-23 escape rule. A generator-owned reserve
  protects this routing corridor during future placement regeneration.
- PN532 pins U2.5/U2.8 now share a short via-free F.Cu DVDD escape. The U2.3
  GND branch terminates directly in the exposed pad, while the retained
  0.45/0.20-mm west GND via keeps U2.3/U2.7/U2.41 tied to the solid plane.
- R201/R202 were moved to a validated vertical side-by-side placement. Native
  D+/D- is complete from the ESP32 through the two series resistors and U16 to
  all four J1 data pads. The MCU side has no vias. A staggered five-via J1
  bridge passes pad, hole, copper and filled-plane DRC; its 0.15-mm clearance
  rule is limited to the fine-pitch connector bridge area.
- U16 is 0.55 mm farther inboard. R102 is fixed as a front-side 0805; its J1-B5
  pull-down path, ground return and U16 pin-6 protection branch are complete.
  CC2 uses two standard 0.50/0.30-mm through vias, outer-layer tracks only and
  a local 0.20-mm clearance rule limited to its C103/C104 centre-gap escape.
  R101 is fixed on B.
- VSYS is complete between U5, both converters and the local bulk capacitors.
  R129 is a hand-friendly 0805 zero-ohm series crossover that keeps SPI_MOSI
  on outer copper while VSYS passes through the constrained charger corridor.
  The two J1 VBUS contacts now join F1 using 0.30-mm front escapes around the
  connector holes, two 0.70/0.35-mm vias and a short reviewed 0.20-mm B.Cu
  shield-corridor neck that widens immediately to 0.50/0.60 mm.
- Three compact KMR221GLFS switches now provide UP/OK/DOWN. SELECT uses
  U9/P07 with R607; BMP390 pin 7 is NC and the sensor remains usable by I2C.
  RESET, BOOT and PAIR retain their dedicated functions.
- Conflicting SPI_SCK/SPI_MOSI/SPI_MISO, I2C_SCL, GPIO44_MCU, NFC_DVDD,
  user-button, IR_LED_A1, IR_LED_K, GPIO43, NFC_LOADMOD, NFC_RESET_N,
  I2C_SDA, PAIR_N, SPI_MOSI_HDR, SPI_SCK_HDR, LF_DOUT_5V and OLED_VCC autorouter copper
  was removed as complete nets, avoiding dangling stubs while those nets wait
  for reviewed routes around USB, the new button strip and the LF island.
- `+5V_RAW` and `+5V_AUX` are fully connected through two narrow L3
  distribution corridors while L2 remains the continuous GND plane. The 36
  requested GND/+3V3 clusters and the reviewed U2.3 GND escape are complete.
- The U8/U11 sensor corridor now carries I2C_SCL from U1.6 to U8.7 through a
  short L3 crossing and I2C_SDA from U8.8 to U11.4 directly on B.Cu. The
  displaced `FG_ALERT_N` and `SPI_MOSI` paths and both local U11 ground
  branches were restored and explicitly connectivity-checked; L2 still has
  no non-GND signal tracks.
- The J5 protection checkpoint connects J5.25 to the complete U25/R732
  `SPI_SCK_HDR` tree and J5.23 to U24.1 on `I2C_SDA_HDR`; the separate R730 SDA
  clamp branch remains open. The two reviewed low-speed L3 crossings preserve
  the ground-only L2 plane. One added `+5V_RAW` stitch via restores the power
  polygon across the SCK clearance slot, and explicit endpoint checks pass for
  both header routes and the two locally rehomed fanouts.
- The PN532 `/NFC_TX2_F` branch now connects L302.2 to C309.1 with five locked
  0.15-mm F.Cu segments, no via and the full reviewed 0.25-mm local clearance.
- The microSD `/SD_CS_DEV` branch now connects U19.1 to J2.2 through one local
  0.45/0.20-mm via. U19.2 retains a complete GND connection through its
  existing plane via after the front escape was shifted toward the card edge.
- The ESP32 `/SPI_MOSI` branch now joins U1.19 to the routed U21/R129 bus group
  with eight locked 0.15-mm outer-layer segments and one 0.45/0.20-mm via.
- The microSD resistor-side `/SPI_MOSI` branch now joins R511.1 to that bus
  group through six locked 0.15-mm L3 segments, one short F.Cu escape and one
  0.45/0.20-mm via. L2 remains ground-only and all critical power groups remain
  connected after the L3 plane refill.
- The USB-C `/USB_CC1` path now joins J1.A5 to 5.1-kohm pull-down R101.1 with
  ten locked outer-layer segments and one 0.45/0.20-mm via. Nine additional
  locked 0.20-mm F.Cu segments join U16.4 to J1.A5 without another via, so all
  three CC1 pads form one connected group.
- The UP-button `/USER_BUTTON_A_N` path now joins SW3.1 to pull-up R608.1
  with ten locked 0.15-mm segments and two 0.45/0.20-mm vias. Its short L3
  crossing clears the dense LF/RGB fanouts; U18.11 remains the second group.
- The back-side `/CELL_POS` monitor branch now joins U8.3 to C120.1 with four
  locked 0.15-mm B.Cu segments and no via.
- The protected `/GPIO43` output R718.2 now reaches expansion-header pad J5.11
  through three locked 0.15-mm L3 segments and one 0.45/0.20-mm tented via.
- The protected `/SPI_MISO_HDR` branch now joins R734.2 to J5 ESD-array pad
  U25.1 with eleven locked 0.15-mm segments, two 0.45/0.20-mm tented vias and
  a reviewed L3 corridor. L2 remains ground-only.
- The PN532 `/NFC_TX1` driver output U2.4 now joins matching inductor L301.1
  through two F.Cu escapes, three locked 0.20-mm L3 segments and two ordinary
  0.45/0.20-mm vias. Reviewed local LF clock/data jogs free the via corridor
  without changing either neighboring net's connectivity; L2 remains GND-only.
- The OLED `/OLED_VCC` supply now joins C615/C616 to J8.16 through one
  0.45/0.20-mm via and a short reviewed L3 crossing. `/OLED_C1P` remains
  connected at the 0.15-mm project minimum, and the local `+5V_AUX` L3 bridge
  retains a single five-pad power group.
- The board currently contains 1881 track segments, 342 vias and 23 zones.
- J2 is 0.175 mm farther inboard than the prior checkpoint. Its signal and
  shell pads now meet the configured 0.50-mm board-edge clearance without
  reducing the adjacent B.Cu ground-track clearance below 0.20 mm.
- DRC: 16 documented non-release findings remain, with no track-width, via,
  drill, short, dangling-track or new routing-clearance finding. Schematic
  parity and ERC are clean; 142 unconnected items remain. GND, +3V3,
  +5V_RAW and +5V_AUX are fully connected.
- The PCB is therefore not order-ready.

## Firmware checkpoint

The three-button PCB change is intentionally hardware-only for now; the
firmware below is the preceding two-button checkpoint and has not been changed.

- PlatformIO/Arduino-ESP32 3.3.8 build succeeds for ESP32-S3 N8R2.
- RAM: 49,568 / 327,680 bytes; application flash: 1,113,399 / 3,342,336 bytes.
- LF power sequencing, HTRC configuration/phase/ANTFAIL diagnosis, ATECC wake
  probe, physical pairing window, web UI, microSD, bounded NEC IR and the
  board-temperature safety policy compile.
- Tag decoding, app authentication, ATECC provisioning and owner recovery are
  not implemented or claimed.

## Outstanding before an order

1. Route the remaining 142 signal connection items, especially the PN532
   supply/matching network and the dense MCU, sensor and microSD corridors.
   Refill planes after each batch and close DRC with no unexplained item.
2. Independently review every footprint, polarity and custom land pattern.
3. Recheck live JLC/LCSC stock, assembly side/class, BOM and CPL rotations.
4. Measure/tune the NFC loop and Sub-GHz network on assembled prototypes.
5. Measure the actual LF coil and select resonance values from phase, current,
   voltage, temperature and range data.
6. Current-limit first power-up and verify charger, protection and all rails
   before connecting an unprotected cell or external equipment.
7. Define and review the phone-app key protocol, reset/recovery flow and ATECC
   slot/lock manifest before irreversible provisioning.
