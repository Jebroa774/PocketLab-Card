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
checkpoint has 1868 track segments, 339 vias and 23 zones. Both `+5V_RAW` and
`+5V_AUX` are complete on narrow L3 corridors, the requested 36 dense-plane
clusters are closed, and the reviewed U2.3 GND escape is routed. R405 is
oriented with pad 1 toward U3 and pad 2 toward the antenna. The microSD socket
is now 0.175 mm farther inboard, eliminating its ten copper-to-edge findings.
J5.25 now reaches the complete U25/R732 `SPI_SCK_HDR` protection tree through
a reviewed short L3 crossing. J5.23 reaches U24.1 on `I2C_SDA_HDR`; its separate
R730 branch remains in the ratsnest. A single reviewed `+5V_RAW` stitch via
keeps the power polygon connected around the SCK clearance slot, and L2 remains
ground-only.
The short PN532 `/NFC_TX2_F` matching branch from L302.2 to C309.1 is now
routed via-free on F.Cu through the reviewed 0.25-mm local corridor.
The microSD controller-side `/SD_CS_DEV` leg now reaches J2.2 through one local
via; the adjacent U19.2 GND escape was shifted toward the card edge without
changing its reviewed plane via.
The ESP32 `/SPI_MOSI` pad U1.19 now reaches the existing U21/R129 shared-bus
trunk through eight locked outer-layer segments and one 0.45/0.20-mm via.
R511.1 now joins that same trunk through six locked 0.15-mm L3 segments, one
short F.Cu escape and one 0.45/0.20-mm via. The route preserves the continuous
L2 ground plane and the connectivity of both protected L3 5-V polygons.
The USB-C `/USB_CC1` receptacle pad J1.A5 now reaches its back-side 5.1-kohm
pull-down R101 through one outer-layer transition. U16.4 now joins that same
group through nine locked 0.20-mm F.Cu segments, so the complete CC1 detection
and ESD branch is connected without another via.
The UP-button `/USER_BUTTON_A_N` contact SW3.1 now reaches pull-up R608.1
through one short reviewed L3 crossing and two 0.45/0.20-mm vias; U18.11
remains the explicit second group on that net.
The back-side `/CELL_POS` monitor input U8.3 now reaches local capacitor C120.1
through four short, via-free 0.15-mm B.Cu segments.
The protected `/GPIO43` output R718.2 now reaches expansion-header pad J5.11
through three locked 0.15-mm L3 segments and one 0.45/0.20-mm tented via.
The protected `/SPI_MISO_HDR` branch now joins resistor R734.2 to J5 ESD-array
channel U25.1 through eleven locked 0.15-mm segments, two 0.45/0.20-mm tented
vias and a reviewed L3 corridor; the dedicated L2 GND plane remains untouched.
KiCad DRC retains 16 documented non-release findings and has no
schematic-parity error; ERC is clean and 144 open items remain. None of these files is an order-ready
fabrication release.

The latest PN532 cleanup connects U2.5/U2.8 with a short via-free DVDD escape
and replaces the old west-side U2.3 GND detour with a direct exposed-pad
connection. `scripts/route_nfc_dvdd_escape.py` reproduces that reviewed stage.

The LF_RFID_EN branch now reaches U22.1 through a reviewed L3 signal corridor.
The change reuses the former redundant +3V3 via site, reconnects R109 to the
retained +3V3 fanout and leaves L2 as a ground-only plane.
`scripts/route_lf_enable.py` reproduces and connectivity-checks this stage.

The dense U8/U11 sensor corridor is also reworked. U8 SCL reaches U1.6 through
two standard 0.45/0.20-mm through-vias and a short L3 crossing, while U8 SDA
reaches U11.4 directly on B.Cu. `FG_ALERT_N` and `SPI_MOSI` were rerouted
around the corridor, the local U11 ground branches were restored, and L2
remains ground-only. `scripts/route_i2c_sensor_corridor.py` reproduces and
connectivity-checks all six affected endpoint pairs.

The reproducible routing helpers are:

```powershell
# Regenerate the placement and inner-plane staging boards
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/build_pcb.py
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/add_planes.py

# Export the full routing DSN
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_pcb.py --export-only --force

# After a reviewed FreeRouting import, apply the local critical-route checkpoint
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_critical.py --force

# Reproduce the reviewed LF_RFID_EN endpoint stage on a candidate board
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_lf_enable.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-lf-enable-candidate.kicad_pcb --force

# Reproduce the reviewed U8/U11 I2C sensor corridor on a candidate board
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_i2c_sensor_corridor.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-i2c-sensor-candidate.kicad_pcb --force

# Reproduce the reviewed via-free PN532 TX2 matching branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_nfc_tx2_matching.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-nfc-tx2-matching-candidate.kicad_pcb --force

# Reproduce the reviewed microSD CS socket leg and local U19 GND rehome
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_sd_cs_socket.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-sd-cs-candidate.kicad_pcb --force

# Reproduce the reviewed ESP32-to-shared-trunk SPI-MOSI branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_spi_mosi_mcu.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-spi-mosi-mcu-candidate.kicad_pcb --force

# Reproduce the reviewed shared-trunk-to-R511 SPI-MOSI branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_spi_mosi_sd_resistor.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-spi-mosi-r511-candidate.kicad_pcb --force

# Reproduce the reviewed U8-to-C120 CELL_POS monitor branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_cell_pos_monitor.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-cell-pos-monitor-candidate.kicad_pcb --force

# Reproduce the reviewed protected GPIO43-to-header branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_gpio43_header.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-gpio43-header-candidate.kicad_pcb --force

# Reproduce the reviewed protected SPI-MISO resistor-to-ESD branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_spi_miso_header_esd.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-spi-miso-header-esd-candidate.kicad_pcb --force

# Reproduce the reviewed USB-C CC1 receptacle-to-pull-down path
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_usb_cc1_resistor.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-usb-cc1-resistor-candidate.kicad_pcb --force

# Reproduce the reviewed USB-C CC1 receptacle-to-U16 ESD branch
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_usb_cc1_esd_branch.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-usb-cc1-esd-candidate.kicad_pcb --force

# Reproduce the reviewed UP-button contact-to-pull-up path
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_user_button_a_pullup.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-user-button-a-candidate.kicad_pcb --force

# Reproduce the reviewed J5 SDA/SCK protection checkpoint as a candidate chain
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_header_bus_protection.py --input PocketLab-Card.kicad_pcb --output PocketLab-Card-header-protection-candidate.kicad_pcb --force
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/rehome_header_neck_fanouts.py --input PocketLab-Card-header-protection-candidate.kicad_pcb --output PocketLab-Card-header-neck-candidate.kicad_pcb --force
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/route_header_sck_bridge.py --input PocketLab-Card-header-neck-candidate.kicad_pcb --output PocketLab-Card-header-sck-bridge-candidate.kicad_pcb --force
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" scripts/bridge_header_sck_power_cut.py --input PocketLab-Card-header-sck-bridge-candidate.kicad_pcb --output PocketLab-Card-header-sck-power-candidate.kicad_pcb --force
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
