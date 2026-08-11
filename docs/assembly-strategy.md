# Assembly and footprint strategy

V1 is a hybrid build. JLCPCB places the small or thermally critical SMT parts;
the owner installs the mechanically large or configurable parts after delivery.
The goal is easy repair and experimentation without compromising power, RF or
LiPo safety.

## Footprint rules

- Default resistors and capacitors: 0805, non-polar where possible.
- RF/NFC matching only: 0603. No 0402 or 0201 parts in V1.
- No BGA or WLCSP packages.
- QFN, DFN, LGA, SOT-563, microSD and the board-level GNSS U.FL are always
  factory assembled.
- Prefer SOIC, TSSOP, SOT-23 and castellated modules for all replaceable parts.
- The current dense placement is deliberately two-sided. Keep hand-reworkable
  parts accessible and verify bottom-side height, reflow and PCBA cost during
  DFM; do not infer side assignment from this document before placement lock.
- Keep ordinary component bodies at least 2.5 mm from the final board edge.
  Edge connectors need process rails and explicit assembler DFM approval.
- Provide 1.0 mm finished holes for the 2.54 mm Dupont-compatible header.
- Use enlarged 0805 hand pads where the layout permits; keep RF reference pads
  compliant with the component datasheet.

## Assembly classes

| Class | Parts | Who installs them |
|---|---|---|
| `JLC_ONLY` | PN532, charger, DC/DCs, fuel gauge, microSD, GNSS U.FL | JLCPCB |
| `JLC_SMT` | GNSS, IR receiver/driver, USB-C, battery connector | JLCPCB preferred, side set by final placement |
| `JLC_OR_HAND` | ESP32 module, TSSOP expanders, SOIC RTC | JLCPCB or careful hand rework |
| `HAND_OR_JLC_SOURCE` | Ebyte Sub-GHz module | Hand install by default |
| `HAND_THT` | 2.54 mm headers and 5 mm IR LED | Owner after delivery |
| `JLC_STANDARD_OPTION` | BMI270 and BMP390 | JLCPCB FULL variant only |

`CORE-ECO` omits U10/U11; `FULL` populates them. Because current placement uses
both PCB sides, neither variant is assumed to qualify for a top-only Economic
PCBA service. Their empty footprints do not make the core board unusable: GNSS
speed/trip logging, NFC, Sub-GHz, IR and microSD remain available.

## Orientation safeguards

- Pin 1 receives both a large silkscreen dot and a copper/fabrication marker.
- Diodes, LEDs, polarized capacitors and battery pins receive `+`, `-`, `A` and
  `K` labels as appropriate; never rely on a footprint outline alone.
- Module outlines include the antenna/keep-out end and the readable part name.
- The board-level U.FL is labeled `GNSS ANT`. U3 pin 6 reaches the lower-edge
  spring through the pi network; the adjacent right-hand pad labeled `868 ANT`
  is the spring's only electrical connection. After soldering and inspection,
  bond the free left end to the upper FR4 pocket wall with a small
  nonconductive epoxy or neutral-cure silicone bridge. Do not solder, ground,
  or add copper at that second mechanical anchor. Perform the final RF tuning
  only after the adhesive has cured and with the enclosure and battery fitted.
- The battery connector is labeled from the wire side as well as the PCB side.
- JLCPCB CPL rotations must be checked visually in its 2D assembly viewer.

## Ordering workflow

1. Recheck every JLC/LCSC part number and stock immediately before ordering.
2. Generate Gerber/drill, BOM and CPL from the tagged KiCad release.
3. Add break-off process rails so tooling holes/fiducials are not drilled into
   the finished card outline.
4. Review both-side BOM/CPL placement in the assembler viewer, then order five
   boards with all `HAND_*` parts DNP.
5. Inspect USB power, 3.3 V, charger and shorts before connecting a LiPo.
6. Install headers and IR LED only after the assembled board passes bring-up.

JLCPCB's library status and assembly class can change. Supplier identifiers in
the preliminary BOM are selection aids, not permission to skip the final BOM
and footprint audit.

Useful current supplier rules:

- [JLCPCB assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)
- [JLCPCB assembly terms and 2.5 mm edge rule](https://jlcpcb.com/help/article/terms-and-conditions-of-jlcpcb-assembly-service)
- [JLCPCB tooling-hole guidance](https://jlcpcb.com/help/article/how-to-add-tooling-holes-for-pcb-assembly-order)
