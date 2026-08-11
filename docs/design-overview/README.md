# PocketLab Card design overview

These KiCad renders show the current 2026-08-11 routing checkpoint, not the
final fabrication appearance. Placement is complete, but 499 connection items
remain open. The IR bodies and spring antenna use approximate mechanical preview
models; the footprint courtyards and board outline remain the manufacturing
references. RF stitching, several sensitive routes and final enclosure
clearances are still open.

## Current views

![Current isometric view](card-isometric.png)

| Top | Bottom |
|---|---|
| ![Current top view](card-top.png) | ![Current bottom view](card-bottom.png) |

The ESP32-S3-WROOM-1-N8R2 shown here remains the V1 controller. ESP32-S31 is a
future V2 candidate and is not part of this PCB revision.

## Visible front-side areas

| Area | Current contents | Enclosure / artwork guidance |
|---|---|---|
| Upper-left | 35 x 27 mm NFC loop | Good visual focus for a printed logo or non-metallic graphic. Do not add metal foil, magnets, conductive paint, screws or a battery over the loop. |
| Upper-right | ESP32-S3 module and PCB antenna | Plastic and ordinary non-conductive ink only around the antenna end. No metal bezel, shield, battery or cable directly over it. |
| Top edge | Side-view 38 kHz IR receiver | Keep a small dark IR-transparent window over its optical face. The body and pads remain inside the card outline. |
| Lower-right | 0.42-inch OLED, PAIR button, main switch and USB area | Provide an OLED window, switch openings and USB access. The battery connector is now on the back. A dark bezel around the display will make the tiny active area look more intentional. |
| Lower-middle | Four 2-mm RGB LEDs, compact UP/OK/DOWN buttons, and adjacent labeled RESET/BOOT service buttons | Use four small windows or one frosted light bar. A three-position membrane can cover the navigation row; keep RESET/BOOT accessible through small service holes. |
| Left short edge | Three flat TSAL6200 IR emitters | All optical faces sit 0.5 mm inside the edge and the lowest body clears the rounded corner. Each vertical 2.54-mm pad pair gives both leads one common 90-degree bend line. Provide one clear opening across the three lenses. |
| Lower edge | Compact 6 x 5 Dupont hole matrix | All 30 connections retain 2.54 mm pitch. Individual Dupont leads and breakaway strips fit; one monolithic 2 x 15 housing does not. |
| Lower-right pocket | 868 MHz helical spring antenna | The 17.3 mm cylindrical spring lies inside an 18.8 x 6.58 mm recess. Its right end is the only electrical solder point; a small nonconductive epoxy or neutral-cure silicone bridge anchors the free left end to the upper FR4 pocket wall. Never solder or ground that free end. Neither spring nor pad exceeds the original card envelope. |

## Back side

The back carries power conversion, protection, sensors, RTC, I/O expanders,
the two-part board-temperature divider beside the 5-V converter,
the removable 125 kHz coil connector and the Sub-GHz module. It is not a flat cosmetic surface. The large apparently
empty region opposite the NFC loop must also remain free of metal and major
components; it is an RF keepout, not spare battery space.

## Practical styling directions

1. **Exposed technical card:** black solder mask, white silkscreen, visible NFC
   loop, dark OLED bezel and translucent RGB light bar.
2. **Thin two-piece shell:** solid front graphic with windows only for OLED,
   buttons, RGB, IR and connectors; the PCB remains serviceable from the back.
3. **Instrument style:** label the four RGB/button positions as modes, use the
   NFC loop as a framed graphic field and reserve the OLED for compact status
   icons rather than text-heavy menus.

The bare PCB is 85.60 x 53.98 x 1.2 mm. The final assembly is not wallet-flat:
without the optional Dupont header, allow roughly 8-9 mm overall until exact
received-part and enclosure measurements replace this provisional envelope.

## Verification status

The current placement and retained routing pass the scripted component/keepout
audit. KiCad DRC reports no routed-geometry, copper-edge or courtyard error and
schematic parity is clean; its six remaining warnings are reviewed footprint-
library comparisons. The 499 unconnected items are the explicit routing blocker,
so this revision must not be sent to fabrication yet.
