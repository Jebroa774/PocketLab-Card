# Hardware design source

## Functional blocks

| Logical block | Contents |
|---|---|
| 00_ROOT | Power domains, buses and hierarchical connections |
| 01_USB_POWER | USB-C, ESD, charger, battery, 3.3 V and 5 V conversion |
| 02_MCU | ESP32-S3-WROOM-1 module, boot/reset and native USB |
| 03_NFC | PN532, clock, matching/RX networks and four-turn PCB loop |
| 04_SUBGHZ | E07-900MM10S CC1101 module, tuneable pi network and inboard spring antenna |
| 05_LF_RFID_SD | HTRC110, removable 125 kHz coil, level shifting, ATECC608C, PAIR and microSD |
| 06_IR_UI | IR transmitter/receiver, RGB LEDs, buttons and bare OLED |
| 07_SENSORS_IO | IMU, barometer, RTC, fuel gauge, U9/U18 and headers |

KiCad 10 is installed locally. `PocketLab-Card.kicad_pro` is the project entry
point and the PCB scaffold contains the exact credit-card outline. The current
generated schematic comprises 274 symbols, 267 assigned footprints and 181
named logical nets (231 physical PCB nets); `reports/erc-current.rpt` reports zero
errors and zero warnings.

The schematic and its machine-readable net description are reproducible with
KiCad's bundled Python:

```powershell
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/generate_schematic.py PocketLab-Card.kicad_sch --design-json design-netlist.json
```

The project-local footprint library includes the manufacturer-derived special
packages and `NFC_Loop_35x27mm_4T_TUNE`. The latter is a four-turn, 0.50/0.50
mm preliminary loop with a 35 x 27 mm copper envelope and a full 36 x 29 mm
all-copper-layer keep-out. Its matching is intentionally not a release value:
measure and tune the populated prototype with the final stack-up, enclosure and
battery using a VNA or suitable NFC fixture.

The tracked `PocketLab-Card.kicad_pcb` is the only authoritative PCB checkpoint.
Generated placement, plane, autorouter and routing-progress boards are deliberately
not versioned because the scripts below recreate them from the schematic,
mechanical template and current rules. This avoids presenting an old intermediate
board as a second design source.

The current PCB contains the guarded digital autorouter fanout plus reviewed local U6/L6,
U7/L7, converter input/output, U7-feedback, RTC-crystal and complete native USB
data routes; L2 remains the uninterrupted ground plane and L3 retains the
power polygons plus explicitly reviewed low-speed signal crossings. R201/R202 are vertical side-by-side 0805
parts, the MCU-side pair stays via-free, and a staggered five-via bridge joins
J1's alternating A/B data pads. U16 is 0.55 mm farther inboard; front-side
0805 R102 now has its J1-B5 pull-down and local ground return routed. The CC2
protection branch to U16 pin 6 is also complete using two ordinary 0.50/0.30-mm
through vias and outer-layer tracks only. SW3/SW7/SW4 are compact, adjacent UP/OK/DOWN
controls; SELECT uses U9/P07 and the BMP390 remains available by I2C polling.
VSYS is now complete through the charger/converter island; an 0805 zero-ohm
SPI_MOSI crossover preserves the plane-only inner layers. Both J1 VBUS contacts
also reach F1 through reviewed local neckdowns and 0.50/0.60-mm B.Cu copper.
The provisional 868-MHz feed now runs through the correctly oriented pi network
and makes its sole signal-layer transition before the spring pocket; its F.Cu
section remains on the narrow PCB bridge outside the notch. The present
checkpoint has 1734 track segments, 327 vias and 23 zones. Both `+5V_RAW` and
`+5V_AUX` are complete on narrow L3 corridors, the requested 36 dense-plane
clusters are closed, and the reviewed U2.3 GND escape is routed. R405 is
oriented with pad 1 toward U3 and pad 2 toward the antenna. The microSD socket
is now 0.175 mm farther inboard, eliminating its ten copper-to-edge findings.
KiCad DRC retains 16 documented non-release findings and has no
schematic-parity error; ERC is clean and 159 open items remain. None of these files is an order-ready
fabrication release.

The latest PN532 cleanup connects U2.5/U2.8 with a short via-free DVDD escape
and replaces the old west-side U2.3 GND detour with a direct exposed-pad
connection. `scripts/route_nfc_dvdd_escape.py` reproduces that reviewed stage.

The reproducible routing helpers are:

```powershell
# Regenerate the placement and inner-plane staging boards
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/build_pcb.py
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/add_planes.py

# Export the full routing DSN
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_pcb.py --export-only --force

# After a reviewed FreeRouting import, apply the local critical-route checkpoint
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_critical.py --force
```

`route_pcb.py` can also run FreeRouting 2.3 with `--jar` and `--java`. Its
separate autorouter DSN physically removes all 42 protected power, USB, RF,
LF and sensitive nets before routing and the SES importer verifies them again.
All files produced by this staging pipeline are ignored by Git; only a deliberately
reviewed result is promoted to `PocketLab-Card.kicad_pcb`.

## Required layout, sourcing and bring-up checks

- USB-C CC resistors and native USB differential pair protection
- Correct ESP32 boot straps and antenna keep-out
- BQ24074 input/current/thermal programming and LiPo polarity
- Stable 3.3 V and 5 V converter compensation/layout per reference designs
- 5 V header current limiting and output discharge
- PN532 DVDD-derived AVDD/TVDD supplies, RX network and measured antenna tuning
- E07-900MM10S pin map, short 50-ohm feed, tuneable pi network and measured 868 MHz spring match; the present lower-right digital corridors must be rearranged before that RF feed is committed
- 18.8 x 6.58 mm spring pocket, 0.6 mm PCB bridge to the sole electrical antenna pad, and a second nonconductive adhesive anchor at the free end
- HTRC110 5 V sequencing, protected short resonant loop and measured 125 kHz coil tuning
- ATECC608C wake/provisioning flow and physical PAIR-button ownership gate
- microSD pull-ups, 47 uF write-transient bulk capacitance and U19 ESD array
- U24/U25 shunt ESD arrays on all five exposed J5 I2C/SPI bus lines
- 100 ohm series protection on 11 direct GPIOs, the GPIO9 temperature probe,
  and the exposed I2C/SPI buses
- R736/RT701 10-kohm divider on GPIO9 for local power-zone temperature
- 220 ohm series protection on all eight expander GPIOs
- optional external 10-kohm NTC on J5 pins 28/30, selected by cutting SJ1
- ER-OLED0.42-1W FPC pinout, fold direction and seven local 0805 capacitors
- SW5 low-current main switch on the TPS63070 enable path
- three independent TSAL6200 current-limit branches and fully inboard formed leads/lenses
- VBUS_USB, VBUS_FUSED, VSYS, +3V3, +5V_RAW and +5V_AUX test points

See `docs/assembly-strategy.md` before selecting or placing any footprint.

## PCB stack target

Four-layer, nominal 1.2 mm FR-4, encoded for the JLC04121H-7628 target:

1. L1: components, RF and short high-speed signals
2. L2: uninterrupted ground plane
3. L3: power polygons and reviewed low-speed signal crossings
4. L4: components and low-speed routing

The encoded build uses 35-um outer copper, 15.2-um inner copper, two 0.2104-mm
7628 prepregs and a 0.665-mm core. USB and Sub-GHz impedance geometry remains
provisional; the LF resonant network must be measured with the actual external
coil and final enclosure before its capacitor values are released.
