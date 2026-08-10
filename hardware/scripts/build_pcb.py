"""Build the netlisted, placement-only PocketLab Card PCB staging file.

The schematic generator is the single source of truth for references,
footprints and pin-to-net assignments.  This script deliberately stops before
routing: it loads the exact mechanical card outline, places every populated
footprint, assigns every schematic net to its pads and writes a separate
``PocketLab-Card-netlisted.kicad_pcb`` file.

Run with KiCad's bundled Python, for example::

    "C:/Program Files/KiCad/10.0/bin/python.exe" hardware/scripts/build_pcb.py

The script refuses to overwrite the project's main PCB.  Its placement checks
are intentionally conservative AABB checks around F/B courtyard geometry.
They are not a replacement for KiCad DRC or a physical prototype review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pcbnew


BOARD_LEFT = 20.0
BOARD_TOP = 20.0
BOARD_RIGHT = 105.6
BOARD_BOTTOM = 73.98
NORMAL_INSET = 0.8
# KiCad courtyards already include package-specific assembly clearance.  This
# is only an extra numerical/placement margin between those courtyards.
PLACEMENT_CLEARANCE = 0.02


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def expanded(self, amount: float) -> "Box":
        return Box(
            self.left - amount,
            self.top - amount,
            self.right + amount,
            self.bottom + amount,
        )

    def intersects(self, other: "Box") -> bool:
        return not (
            self.right <= other.left
            or self.left >= other.right
            or self.bottom <= other.top
            or self.top >= other.bottom
        )

    def inside(self, other: "Box") -> bool:
        return (
            self.left >= other.left
            and self.top >= other.top
            and self.right <= other.right
            and self.bottom <= other.bottom
        )


@dataclass(frozen=True)
class Region:
    side: str
    box: Box


@dataclass(frozen=True)
class FixedPlacement:
    reference: str
    side: str
    x_mm: float
    y_mm: float
    rotation_deg: float = 0.0
    use_origin: bool = False
    allow_edge: bool = False
    blocks_both_sides: bool = False


@dataclass(frozen=True)
class Occupied:
    reference: str
    side: str
    box: Box


# AE1 contains the complete four-turn winding.  Its 36.1 x 29.1 mm physical
# envelope is a component keepout on *both* sides, including the inner opening;
# this is stricter than merely reserving the copper annulus.
NFC_OUTER = Box(22.85, 23.45, 58.95, 52.55)

# The project-local U1 footprint has a physical assembly courtyard, while its
# original all-layer antenna rule area remains unchanged.  Keep this explicit
# body model as an independent placement assertion and reserve the antenna end
# on both PCB sides.
ESP_BODY = Box(83.5, 20.0, 101.7, 45.6)
# Stock ESP32-S3-WROOM-1 embeds an all-layer footprint keepout extending 24 mm
# left/right around its antenna end.  At the fixed module position only the
# board-interior portion below is relevant.
ESP_ANTENNA = Box(68.5, 20.0, 105.6, 26.2)


FIXED_PLACEMENTS: tuple[FixedPlacement, ...] = (
    FixedPlacement("AE1", "F", 40.9, 38.0, 0.0, False, False, True),
    # RF modules and their external antenna connectors.
    # Shift U1 0.40 mm left to create a manufacturable front-side microSD
    # protection strip.  R203 follows by the same amount.
    FixedPlacement("U1", "F", 92.6, 32.75, 0.0, True, True, False),
    # GNSS is a straight edge-fed chain: J3 -> D501 -> U4 pin 11.  The DNP
    # active-antenna bias branch is kept immediately beside that line.
    FixedPlacement("U4", "F", 33.2, 59.5, 180.0),
    FixedPlacement("U17", "B", 40.5, 55.5),
    FixedPlacement("J3", "F", 22.5, 56.2, 180.0, True, True, True),
    FixedPlacement("D501", "F", 25.9, 56.2),
    FixedPlacement("L501", "F", 26.2, 59.0, 90.0),
    FixedPlacement("R505", "F", 26.2, 62.6, 90.0),
    FixedPlacement("C504", "F", 24.0, 60.7, 90.0),
    # GNSS supply/load-switch support and UART source damping.  Back-side
    # angles are chosen so the serialized physical orientations match the
    # comments below after KiCad's footprint flip.
    FixedPlacement("R501", "B", 37.85, 55.175, 90.0),
    FixedPlacement("C501", "B", 39.0, 58.4, 180.0),
    FixedPlacement("C502", "B", 42.7, 58.4, 180.0),
    FixedPlacement("R502", "B", 34.2, 53.8),
    FixedPlacement("R506", "B", 43.9, 55.9, 180.0),
    FixedPlacement("R507", "B", 36.0, 63.0, 180.0),
    # Rotate U3 about the centre of its existing envelope so the digital row
    # faces the routing channel at y=53; its IPEX remains clear from J5/IR.
    FixedPlacement("U3", "B", 82.0, 67.0, 180.0, True, False, False),
    # Edge connectors and through-hole user interfaces.
    FixedPlacement("J1", "F", 102.6, 51.7, 90.0, True, True, True),
    # Rotate the USB protector so its N/P pins face J1 in the same physical
    # order as the MCU pair.  The 22-ohm resistors sit immediately below U1;
    # pad 2 faces the MCU and the 0.26 mm courtyard gaps remain DRC-clean.
    FixedPlacement("U16", "F", 94.8, 48.5, 180.0),
    FixedPlacement("R201", "F", 85.5, 47.5, 180.0),
    FixedPlacement("R202", "F", 85.5, 49.75, 180.0),
    # Keep the ESP32 enable network and supply decoupling beside the module
    # instead of allowing them to occupy the USB breakout channel.
    FixedPlacement("C202", "F", 81.2, 28.0, 180.0),
    FixedPlacement("C203", "F", 77.5, 28.0, 180.0),
    FixedPlacement("R203", "F", 81.4, 31.4, 180.0),
    FixedPlacement("C201", "F", 79.8, 33.7, 180.0),
    FixedPlacement("J4", "F", 102.1, 65.5, 90.0, True, True, True),
    FixedPlacement("J7", "F", 85.5, 70.0),
    FixedPlacement("J5", "F", 59.0, 69.45, 270.0, True, True, True),
    FixedPlacement("D1", "F", 75.0, 72.0, 90.0, True, True, True),
    FixedPlacement("U13", "F", 65.0, 71.0, 0.0, False, True),
    # Edge-access microSD under the ESP body.  Electrical pads retain
    # 0.325 mm copper-to-edge clearance; the card intentionally projects out.
    FixedPlacement("J2", "B", 99.25, 39.0, 90.0, False, True, False),
    # NFC controller just outside the loop annulus.
    FixedPlacement("U2", "F", 65.0, 42.6),
    # Keep the 27.12 MHz Pierce oscillator directly below U2.  The two load
    # capacitors face the crystal signal pads while their ground pads remain
    # exposed for very short stitching vias into the L2 ground plane.
    FixedPlacement("Y301", "F", 65.0, 48.4),
    FixedPlacement("C306", "F", 61.8, 48.1, 90.0),
    FixedPlacement("C307", "F", 68.2, 48.1, 270.0),
    FixedPlacement("L301", "F", 61.0, 37.0, 90.0),
    FixedPlacement("L302", "F", 65.0, 37.0, 90.0),
    FixedPlacement("C308", "F", 68.0, 36.0),
    FixedPlacement("C309", "F", 68.0, 33.0),
    # C311 is a DNP NFC tuning option.  Fix it in the NFC bank so the generic
    # placer cannot put it directly in front of U1's USB pins.
    FixedPlacement("C311", "F", 78.0, 38.5),
    FixedPlacement("R303", "F", 47.0, 22.2),
    FixedPlacement("R304", "F", 39.5, 22.2),
    # Visible controls occupy the strip below the complete NFC keepout.
    FixedPlacement("LED1", "F", 42.0, 63.0),
    FixedPlacement("LED2", "F", 48.0, 63.0),
    FixedPlacement("LED3", "F", 54.0, 63.0),
    FixedPlacement("LED4", "B", 86.0, 33.0),
    FixedPlacement("SW3", "F", 44.0, 56.0),
    FixedPlacement("SW4", "F", 54.0, 56.0),
    # Strap/NFC test pads remain accessible on the front, but outside the
    # coupled USB escape corridor along U1's lower-left corner.
    FixedPlacement("TP201", "F", 62.0, 52.0),
    FixedPlacement("TP202", "F", 65.0, 52.0),
    FixedPlacement("TP203", "F", 60.3, 54.5),
    FixedPlacement("TP301", "F", 60.3, 57.5),
    # ESP service buttons and the high-current IR/buzzer hardware.
    FixedPlacement("SW1", "F", 75.0, 48.0),
    FixedPlacement("SW2", "B", 56.5, 56.0),
    # Put the IR pulse buffer, series resistor, LED and MOSFET in one local
    # current loop.  R601 pad 2 faces D1; the two gate resistors sit beside Q1.
    FixedPlacement("C607", "F", 79.5, 63.0),
    FixedPlacement("C608", "F", 79.5, 59.8),
    FixedPlacement("R601", "F", 75.0, 63.5, 270.0),
    FixedPlacement("Q1", "F", 80.3, 68.4, 270.0),
    FixedPlacement("R602", "F", 84.0, 65.4, 180.0),
    FixedPlacement("R603", "F", 80.3, 65.4, 180.0),
    FixedPlacement("BZ1", "F", 91.0, 57.0),
    FixedPlacement("Q4", "F", 91.0, 64.0),
    # U3 local SPI and supply parts sit on F.Cu opposite its rotated digital
    # row.  Short vias land directly beside the module pads on B.Cu.
    FixedPlacement("R403", "F", 69.0, 53.0),
    FixedPlacement("R406", "F", 73.0, 53.0, 180.0),
    FixedPlacement("R402", "F", 69.8, 56.0, 90.0),
    FixedPlacement("R401", "F", 72.2, 56.0, 90.0),
    FixedPlacement("R404", "F", 74.6, 56.0, 90.0),
    FixedPlacement("C401", "F", 66.5, 67.0, 180.0),
    FixedPlacement("C402", "F", 70.2, 63.5, 180.0),
    # USB input protection and charger.  The high-frequency IN/BAT/OUT
    # capacitors face their U5 pins; programming and default resistors remain
    # in the same right-side power island rather than at the far board edge.
    FixedPlacement("F1", "B", 94.9, 47.1),
    FixedPlacement("D101", "B", 90.2, 47.1),
    # Pin 13 (VBUS) faces the connector-side capacitors, CELL_POS faces the
    # two-capacitor row below, and VSYS faces the converter-side capacitors.
    FixedPlacement("U5", "B", 90.2, 50.5, 90.0),
    FixedPlacement("C103", "B", 94.15, 52.0, 180.0),
    FixedPlacement("C106", "B", 94.15, 49.75, 180.0),
    FixedPlacement("C104", "B", 92.4, 54.1),
    FixedPlacement("C121", "B", 88.8, 54.1),
    FixedPlacement("C105", "B", 86.9, 50.5, 90.0),
    FixedPlacement("C122", "B", 86.8, 46.8, 90.0),
    # Keep the four analogue charger-programming resistors immediately below
    # U5.  Quiet status/default pulls remain with the region placer so the
    # reserved microSD bulk-capacitor slot is not consumed by fixed power parts.
    FixedPlacement("R111", "B", 85.2, 54.0),
    FixedPlacement("R112", "B", 85.2, 56.2),
    FixedPlacement("R113", "B", 88.9, 57.2),
    FixedPlacement("R114", "B", 92.6, 57.2),
    FixedPlacement("R128", "B", 90.6, 32.0),
    # TPS63070: retain the compact dual switch-node geometry and move the HF
    # bypasses plus control/feedback components into the newly opened gap.
    FixedPlacement("U6", "B", 67.0, 44.0),
    FixedPlacement("L6", "B", 62.5, 44.0, 90.0),
    FixedPlacement("C108", "B", 62.0, 39.8),
    FixedPlacement("C123", "B", 66.6, 40.8, 180.0),
    FixedPlacement("C124", "B", 67.95, 47.62, 270.0),
    FixedPlacement("C107", "B", 70.55, 44.6, 180.0),
    FixedPlacement("R116", "B", 70.3, 41.2, 90.0),
    FixedPlacement("R117", "B", 70.4, 47.4, 90.0),
    FixedPlacement("R118", "B", 73.15, 47.7, 180.0),
    FixedPlacement("R119", "B", 72.8, 41.6, 90.0),
    FixedPlacement("C110", "B", 60.8, 49.8),
    FixedPlacement("C111", "B", 64.5, 50.8),
    FixedPlacement("C112", "B", 68.2, 51.1),
    # TPS61023: move the complete island right, freeing U6's quiet feedback
    # side.  C113 is physically parallel to R120 and both divider parts face
    # U7.1; R403/R404 are moved below the island.
    FixedPlacement("U7", "B", 81.5, 44.0),
    FixedPlacement("L7", "B", 77.0, 44.0),
    FixedPlacement("C113", "B", 86.4, 41.8, 270.0),
    FixedPlacement("R120", "B", 84.5, 41.8, 270.0),
    FixedPlacement("R121", "B", 84.5, 45.5, 270.0),
    FixedPlacement("R122", "B", 84.0, 51.1),
    FixedPlacement("C114", "B", 81.1, 47.5),
    FixedPlacement("C115", "B", 81.3, 41.65, 180.0),
    FixedPlacement("C116", "B", 77.4, 51.1),
    # Header load switch, current-limit resistor and bypasses form their own
    # compact island.  Rotation puts IN on the left and OUT on the right.
    FixedPlacement("U15", "B", 94.5, 60.3, 180.0),
    FixedPlacement("C117", "B", 88.9, 60.8),
    FixedPlacement("C119", "B", 95.9, 63.9, 90.0),
    FixedPlacement("C118", "B", 95.9, 67.8, 90.0),
    FixedPlacement("R123", "B", 88.9, 63.1),
    FixedPlacement("R124", "B", 88.1, 37.0, 90.0),
    FixedPlacement("R127", "B", 91.2, 28.0, 90.0),
    FixedPlacement("U8", "B", 82.0, 36.5),
    FixedPlacement("C120", "B", 81.7, 39.3),
    # Cell protection follows the physical current order
    # GND -> Q3 -> common drains -> Q2 -> CELL_NEG/J4.
    FixedPlacement("U14", "B", 88.0, 65.5),
    FixedPlacement("C102", "B", 85.6, 65.75, 270.0),
    FixedPlacement("R104", "B", 91.0, 65.6),
    FixedPlacement("R105", "B", 85.2, 62.7),
    FixedPlacement("Q3", "B", 88.45, 71.0, 180.0),
    FixedPlacement("Q2", "B", 92.8, 71.0),
    FixedPlacement("R107", "B", 88.7, 67.8),
    FixedPlacement("R106", "B", 92.4, 67.8),
    # Sensors and expanders use the upper-right back side; the complete NFC
    # loop opening remains empty on both sides.  Keep every local bypass part
    # beside its IC instead of leaving it to the generic block placer.
    FixedPlacement("U9", "B", 64.0, 31.0),
    FixedPlacement("C701", "B", 61.3, 24.8, 90.0),
    FixedPlacement("R703", "B", 64.8, 24.5),
    FixedPlacement("U18", "B", 75.0, 29.5),
    FixedPlacement("C707", "B", 80.95, 27.5, 180.0),
    FixedPlacement("R701", "B", 69.2, 28.0, 90.0),
    FixedPlacement("R702", "B", 69.2, 31.8, 90.0),
    FixedPlacement("U10", "B", 72.0, 36.0),
    FixedPlacement("C703", "B", 72.0, 33.317, 180.0),
    FixedPlacement("C702", "B", 70.5, 38.65),
    FixedPlacement("U11", "B", 78.0, 35.7),
    FixedPlacement("C704", "B", 78.0, 33.335, 180.0),
    FixedPlacement("C705", "B", 78.0, 38.2),
    FixedPlacement("TP703", "B", 66.0, 37.2),
    FixedPlacement("TP701", "B", 81.25, 31.2),
    FixedPlacement("TP702", "B", 86.0, 37.0),
    # Moving J2 to the right edge opens a quiet lower-left RTC island.  The
    # two crystal paths remain symmetric and C706 faces the RTC supply pin.
    FixedPlacement("U12", "B", 50.5, 62.0, 180.0),
    FixedPlacement("Y701", "B", 45.3, 63.27, 270.0),
    FixedPlacement("C706", "B", 56.2, 63.9, 180.0),
    # Direct MCU GPIO resistors use every remaining source-side pocket around
    # U1/J1.  The four right-edge parts stay above J4's through-hole volume;
    # the longer GPIO41-44 stubs are an explicit density compromise.
    FixedPlacement("R710", "B", 103.0, 27.75, 180.0),
    FixedPlacement("R711", "B", 99.5, 27.75),
    FixedPlacement("R712", "B", 88.75, 29.0, 90.0),
    FixedPlacement("R713", "F", 81.0, 52.25, 270.0),
    FixedPlacement("R714", "F", 78.25, 52.25, 180.0),
    FixedPlacement("R715", "B", 96.0, 27.75),
    FixedPlacement("R716", "F", 100.25, 59.0, 270.0),
    FixedPlacement("R717", "F", 102.5, 59.0, 270.0),
    FixedPlacement("R718", "F", 83.75, 52.25, 180.0),
    FixedPlacement("R719", "F", 98.0, 59.0, 270.0),
    FixedPlacement("R720", "F", 84.5, 57.25, 270.0),
    FixedPlacement("R721", "F", 81.25, 55.0, 180.0),
    # The TCA9535 protection bank fits in the 2.82-mm top strip, outside both
    # the NFC component reservation and ESP antenna keepout.
    FixedPlacement("R722", "B", 66.6, 21.82, 180.0),
    FixedPlacement("R723", "B", 62.9, 21.82, 180.0),
    FixedPlacement("R724", "B", 59.2, 21.82),
    FixedPlacement("R725", "B", 55.5, 21.82),
    FixedPlacement("R726", "B", 51.8, 21.82),
    FixedPlacement("R727", "B", 48.1, 21.82),
    FixedPlacement("R728", "B", 44.4, 21.82),
    FixedPlacement("R729", "B", 40.7, 21.82),
    # Header-side I2C/SPI damping remains immediately above J5 while leaving
    # the GNSS module and planned four-LED/capacitor row clear.
    FixedPlacement("R730", "F", 33.2, 66.5, 180.0),
    FixedPlacement("R731", "F", 36.7, 66.5, 180.0),
    FixedPlacement("R732", "F", 29.7, 66.5, 180.0),
    FixedPlacement("R733", "F", 26.2, 66.5),
    FixedPlacement("R734", "F", 22.7, 66.5),
    # J2 crosses immediately to the front-side ESD bank.  R510-R512 remain at
    # the ESP source; card-driven MISO is damped by R513 directly below U19.
    FixedPlacement("U19", "F", 103.85, 38.5, 90.0, False, True, False),
    FixedPlacement("R510", "F", 81.45, 38.92, 180.0),
    FixedPlacement("R511", "F", 89.0, 47.8, 270.0),
    FixedPlacement("R512", "F", 91.2, 47.8, 270.0),
    FixedPlacement("R513", "F", 103.1, 42.55, 90.0),
    # C510/C511 are local at the edge.  The larger C512 stays 1210 and uses
    # the solid L3 rail as lower-frequency write-current storage.
    FixedPlacement("C512", "B", 85.25, 29.0),
    FixedPlacement("C510", "F", 104.3, 34.47, 90.0, False, True, False),
    FixedPlacement("C511", "F", 104.3, 30.8, 90.0, False, True, False),
)


GNSS_FRONT = Region("F", Box(59.7, 20.9, 82.8, 32.0))
NFC_FRONT = Region("F", Box(59.7, 32.0, 82.8, 46.0))
MCU_FRONT_SIDE = Region("F", Box(74.5, 29.0, 83.0, 46.0))
MCU_FRONT_BOTTOM = Region("F", Box(71.0, 46.0, 97.0, 52.4))
LOWER_FRONT_LEFT = Region("F", Box(24.8, 53.0, 61.0, 66.8))
LOWER_FRONT_RIGHT = Region("F", Box(62.0, 52.8, 97.0, 70.3))
SD_BACK = Region("B", Box(21.0, 52.8, 61.0, 66.8))
SUBGHZ_BACK = Region("B", Box(60.0, 47.0, 83.0, 52.4))
POWER_BUCK_BACK = Region("B", Box(60.0, 28.8, 82.8, 40.2))
POWER_BOOST_BACK = Region("B", Box(60.0, 39.8, 82.8, 52.4))
POWER_RIGHT_BACK = Region("B", Box(83.3, 46.0, 104.7, 72.8))
POWER_MID_BACK = Region("B", Box(60.0, 28.8, 82.8, 52.4))
RIGHT_BACK_TOP = Region("B", Box(59.7, 20.8, 82.8, 52.4))
BACK_UNDER_ESP_BODY = Region("B", Box(84.0, 28.8, 104.7, 45.4))
TOP_FRONT_STRIP = Region("F", Box(24.0, 20.8, 58.8, 23.4))
TOP_BACK_STRIP = Region("B", Box(24.0, 20.8, 58.8, 23.4))


ALLOWED_EXTRA_PADS = {
    "J1": {"A8", "B8"},  # USB2-only symbol intentionally omits SBU1/SBU2.
    "J4": {"MP"},  # JST shell/mounting pads are mechanical.
}


def vec_mm(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x_mm, y_mm)


def footprint_root() -> Path:
    return Path(sys.executable).resolve().parent.parent / "share" / "kicad" / "footprints"


def natural_key(value: str) -> list[object]:
    return [int(token) if token.isdigit() else token for token in re.split(r"(\d+)", value)]


def field_is_true(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def root_local_net_name(logical_name: object) -> str:
    """Return KiCad's physical name for a local label on the root sheet."""
    name = str(logical_name)
    if not name or name.startswith("/"):
        raise RuntimeError(f"Expected an unscoped logical net name, got {name!r}")
    return f"/{name}"


def pin_board_net_name(
    part: dict[str, object], pin_number: object, logical_name: object
) -> str:
    if logical_name is not None and str(logical_name):
        return root_local_net_name(logical_name)
    pin = str(pin_number)
    no_connect_nets = {
        str(number): str(name)
        for number, name in dict(part.get("no_connect_nets", {})).items()
    }
    try:
        return no_connect_nets[pin]
    except KeyError as exc:
        raise RuntimeError(
            f"{part.get('reference', '?')}.{pin}: missing generated no-connect net name"
        ) from exc


def load_design(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != 1 or not isinstance(payload.get("parts"), list):
        raise RuntimeError(f"Unsupported or invalid design netlist: {path}")
    parts = payload["parts"]
    references = [str(part["reference"]) for part in parts]
    duplicates = sorted({ref for ref in references if references.count(ref) > 1})
    if duplicates:
        raise RuntimeError("Duplicate references in design netlist: " + ", ".join(duplicates))
    return parts


def load_footprint(hardware_dir: Path, part: dict[str, object]) -> pcbnew.FOOTPRINT:
    footprint_id = str(part.get("footprint", ""))
    if not footprint_id:
        raise RuntimeError(f"{part['reference']} has no footprint")
    try:
        library, name = footprint_id.split(":", 1)
    except ValueError as exc:
        raise RuntimeError(f"Invalid footprint ID for {part['reference']}: {footprint_id}") from exc

    if library == "PocketLab_Custom":
        library_dir = hardware_dir / "PocketLab_Custom.pretty"
    elif library == "PocketLab_Card":
        library_dir = hardware_dir / "footprints" / "PocketLab_Card.pretty"
    else:
        library_dir = footprint_root() / f"{library}.pretty"
    try:
        footprint = pcbnew.FootprintLoad(str(library_dir), name)
    except Exception as exc:
        raise RuntimeError(
            f"KiCad failed loading footprint for {part['reference']}: {footprint_id} "
            f"from {library_dir}"
        ) from exc
    if footprint is None:
        raise RuntimeError(f"Footprint not found for {part['reference']}: {footprint_id}")

    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetReference(str(part["reference"]))
    footprint.SetValue(str(part["value"]))
    footprint.Value().SetVisible(False)
    fields = {str(name): str(value) for name, value in dict(part.get("fields", {})).items()}
    footprint.SetFields(fields)
    for field_name in fields:
        footprint.GetField(field_name).SetVisible(False)
    footprint.SetDNP(bool(part.get("dnp", field_is_true(fields.get("DNP", "")))))
    footprint.SetExcludedFromBOM(not bool(part.get("in_bom", True)))
    return footprint


def validate_footprint_pads(part: dict[str, object], footprint: pcbnew.FOOTPRINT) -> None:
    reference = str(part["reference"])
    schematic_pins = set(str(pin) for pin in dict(part["pins"]))
    footprint_pads = {pad.GetNumber() for pad in footprint.Pads() if pad.GetNumber()}

    missing = sorted(schematic_pins - footprint_pads, key=natural_key)
    if missing:
        raise RuntimeError(
            f"{reference}: schematic pins missing from footprint: {', '.join(missing)}"
        )

    unexpected = footprint_pads - schematic_pins - ALLOWED_EXTRA_PADS.get(reference, set())
    if unexpected:
        raise RuntimeError(
            f"{reference}: unexpected numbered footprint pads: "
            + ", ".join(sorted(unexpected, key=natural_key))
        )


def create_nets(board: pcbnew.BOARD, parts: Sequence[dict[str, object]]) -> dict[str, pcbnew.NETINFO_ITEM]:
    names = sorted(
        {
            pin_board_net_name(part, pin, net_name)
            for part in parts
            for pin, net_name in dict(part["pins"]).items()
        }
    )
    result: dict[str, pcbnew.NETINFO_ITEM] = {}
    for name in names:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        result[name] = net
    return result


def assign_pad_nets(
    part: dict[str, object], footprint: pcbnew.FOOTPRINT, nets: dict[str, pcbnew.NETINFO_ITEM]
) -> None:
    by_number: dict[str, list[pcbnew.PAD]] = {}
    for pad in footprint.Pads():
        by_number.setdefault(pad.GetNumber(), []).append(pad)

    for pin, net_name_value in dict(part["pins"]).items():
        net_name = pin_board_net_name(part, pin, net_name_value)
        for pad in by_number[str(pin)]:
            pad.SetNet(nets[net_name])


def reset_to_front(footprint: pcbnew.FOOTPRINT) -> None:
    if footprint.GetLayer() == pcbnew.B_Cu:
        footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    footprint.SetOrientationDegrees(0.0)
    footprint.SetPosition(vec_mm(0.0, 0.0))


def configure_side_and_rotation(
    footprint: pcbnew.FOOTPRINT, side: str, rotation_deg: float
) -> None:
    reset_to_front(footprint)
    footprint.SetOrientationDegrees(rotation_deg)
    if side == "B":
        footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if side not in {"F", "B"}:
        raise ValueError(f"Invalid side {side!r}")


def courtyard_box(footprint: pcbnew.FOOTPRINT, side: str) -> Box:
    footprint.BuildCourtyardCaches()
    layer = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    bounds = footprint.GetCourtyard(layer).BBox()
    if bounds.GetWidth() <= 0 or bounds.GetHeight() <= 0:
        bounds = footprint.GetBoundingBox(False, False)
    return Box(
        pcbnew.ToMM(bounds.GetLeft()),
        pcbnew.ToMM(bounds.GetTop()),
        pcbnew.ToMM(bounds.GetRight()),
        pcbnew.ToMM(bounds.GetBottom()),
    )


def center_footprint(
    footprint: pcbnew.FOOTPRINT, side: str, x_mm: float, y_mm: float, rotation_deg: float
) -> Box:
    configure_side_and_rotation(footprint, side, rotation_deg)
    footprint.SetPosition(vec_mm(x_mm, y_mm))
    initial = courtyard_box(footprint, side)
    delta_x = x_mm - (initial.left + initial.right) / 2.0
    delta_y = y_mm - (initial.top + initial.bottom) / 2.0
    footprint.Move(vec_mm(delta_x, delta_y))
    return courtyard_box(footprint, side)


def place_at_origin(
    footprint: pcbnew.FOOTPRINT, side: str, x_mm: float, y_mm: float, rotation_deg: float
) -> Box:
    configure_side_and_rotation(footprint, side, rotation_deg)
    footprint.SetPosition(vec_mm(x_mm, y_mm))
    return courtyard_box(footprint, side)


def set_reference_style(footprint: pcbnew.FOOTPRINT, side: str) -> None:
    """Keep dense reference designators on assembly/Fab, not production silk."""
    bounds = courtyard_box(footprint, side)
    reference = footprint.Reference()
    reference.SetVisible(True)
    reference.SetLayer(pcbnew.F_Fab if side == "F" else pcbnew.B_Fab)
    reference.SetTextSize(vec_mm(0.8, 0.8))
    reference.SetTextThickness(pcbnew.FromMM(0.12))
    reference.SetPosition(vec_mm((bounds.left + bounds.right) / 2.0, bounds.top - 0.38))


def normal_board_box() -> Box:
    return Box(
        BOARD_LEFT + NORMAL_INSET,
        BOARD_TOP + NORMAL_INSET,
        BOARD_RIGHT - NORMAL_INSET,
        BOARD_BOTTOM - NORMAL_INSET,
    )


def violates_reserved_area(reference: str, box: Box) -> str | None:
    if reference != "U1" and box.expanded(PLACEMENT_CLEARANCE).intersects(ESP_ANTENNA):
        return "ESP32 antenna keepout"
    if reference != "AE1" and box.expanded(PLACEMENT_CLEARANCE).intersects(NFC_OUTER):
        return "complete NFC loop component keepout"
    return None


def collision_with(
    reference: str, side: str, box: Box, occupied: Sequence[Occupied]
) -> Occupied | None:
    candidate = box.expanded(PLACEMENT_CLEARANCE)
    for item in occupied:
        # J2 intentionally spans the B-side projection of U1's embedded pad-41
        # thermal vias.  Those 0.20 mm holes omit B.Mask and are fully tented;
        # the nearest J2 shell copper starts 0.40 mm beyond the shifted via
        # array.  Retain every U1 via as an obstacle for all other footprints.
        reviewed_tented_via_overlap = (
            reference == "J2" and item.reference == "U1.PTH41"
        )
        if (
            item.side == side
            and not reviewed_tented_via_overlap
            and candidate.intersects(item.box)
        ):
            return item
    return None


def register_placement(
    occupied: list[Occupied],
    reference: str,
    side: str,
    box: Box,
    blocks_both_sides: bool = False,
) -> None:
    occupied.append(Occupied(reference, side, box))
    if blocks_both_sides:
        occupied.append(Occupied(reference, "B" if side == "F" else "F", box))


def through_hole_boxes(footprint: pcbnew.FOOTPRINT) -> list[tuple[str, Box]]:
    result: list[tuple[str, Box]] = []
    for index, pad in enumerate(footprint.Pads()):
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
            continue
        bounds = pad.GetBoundingBox()
        result.append(
            (
                pad.GetNumber() or str(index),
                Box(
                    pcbnew.ToMM(bounds.GetLeft()),
                    pcbnew.ToMM(bounds.GetTop()),
                    pcbnew.ToMM(bounds.GetRight()),
                    pcbnew.ToMM(bounds.GetBottom()),
                ),
            )
        )
    return result


def pth_collision(
    footprint: pcbnew.FOOTPRINT,
    reference: str,
    side: str,
    occupied: Sequence[Occupied],
) -> tuple[str, Occupied] | None:
    opposite = "B" if side == "F" else "F"
    for pad_number, box in through_hole_boxes(footprint):
        collision = collision_with(reference, opposite, box, occupied)
        if collision:
            return pad_number, collision
    return None


def register_pth_obstacles(
    occupied: list[Occupied], footprint: pcbnew.FOOTPRINT, reference: str, side: str
) -> None:
    opposite = "B" if side == "F" else "F"
    for pad_number, box in through_hole_boxes(footprint):
        occupied.append(Occupied(f"{reference}.PTH{pad_number}", opposite, box))


def place_fixed(
    footprint: pcbnew.FOOTPRINT,
    placement: FixedPlacement,
    occupied: list[Occupied],
) -> Box:
    if placement.reference == "U1":
        place_at_origin(
            footprint,
            placement.side,
            placement.x_mm,
            placement.y_mm,
            placement.rotation_deg,
        )
        box = ESP_BODY
    elif placement.use_origin:
        box = place_at_origin(
            footprint,
            placement.side,
            placement.x_mm,
            placement.y_mm,
            placement.rotation_deg,
        )
    else:
        box = center_footprint(
            footprint,
            placement.side,
            placement.x_mm,
            placement.y_mm,
            placement.rotation_deg,
        )

    reserved = violates_reserved_area(placement.reference, box)
    if reserved:
        raise RuntimeError(f"Fixed placement {placement.reference} intersects {reserved}: {box}")
    if not placement.allow_edge and not box.inside(normal_board_box()):
        raise RuntimeError(f"Fixed placement {placement.reference} crosses board inset: {box}")
    collision = collision_with(placement.reference, placement.side, box, occupied)
    if collision:
        raise RuntimeError(
            f"Fixed placement {placement.reference} overlaps {collision.reference} on "
            f"{placement.side}: {box} vs {collision.box}"
        )
    opposite = "B" if placement.side == "F" else "F"
    if placement.blocks_both_sides:
        opposite_collision = collision_with(placement.reference, opposite, box, occupied)
        if opposite_collision:
            raise RuntimeError(
                f"Fixed placement {placement.reference} volume overlaps "
                f"{opposite_collision.reference} on {opposite}"
            )
    else:
        pad_collision = pth_collision(
            footprint, placement.reference, placement.side, occupied
        )
        if pad_collision:
            pad_number, item = pad_collision
            raise RuntimeError(
                f"Fixed placement {placement.reference} PTH {pad_number} overlaps "
                f"{item.reference} on {opposite}"
            )
    register_placement(
        occupied,
        placement.reference,
        placement.side,
        box,
        placement.blocks_both_sides,
    )
    if not placement.blocks_both_sides:
        register_pth_obstacles(
            occupied, footprint, placement.reference, placement.side
        )
    set_reference_style(footprint, placement.side)
    return box


def candidate_centers(region: Box, width: float, height: float) -> Iterable[tuple[float, float]]:
    x_start = region.left + width / 2.0
    x_stop = region.right - width / 2.0
    y_start = region.top + height / 2.0
    y_stop = region.bottom - height / 2.0
    if x_start > x_stop or y_start > y_stop:
        return
    step = 0.5
    y = y_start
    while y <= y_stop + 1e-6:
        x = x_start
        while x <= x_stop + 1e-6:
            yield round(x, 3), round(y, 3)
            x += step
        y += step


def place_in_regions(
    footprint: pcbnew.FOOTPRINT,
    reference: str,
    regions: Sequence[Region],
    occupied: list[Occupied],
) -> tuple[str, Box]:
    for region in regions:
        for rotation in (0.0, 90.0):
            probe = center_footprint(footprint, region.side, 0.0, 0.0, rotation)
            for x_mm, y_mm in candidate_centers(region.box, probe.width, probe.height):
                box = center_footprint(footprint, region.side, x_mm, y_mm, rotation)
                if not box.inside(region.box) or not box.inside(normal_board_box()):
                    continue
                if violates_reserved_area(reference, box):
                    continue
                if collision_with(reference, region.side, box, occupied):
                    continue
                if pth_collision(footprint, reference, region.side, occupied):
                    continue
                register_placement(occupied, reference, region.side, box)
                register_pth_obstacles(occupied, footprint, reference, region.side)
                set_reference_style(footprint, region.side)
                return region.side, box
    raise RuntimeError(
        f"No collision-free placement found for {reference} in "
        + ", ".join(f"{region.side}:{region.box}" for region in regions)
    )


def refs(*values: str) -> set[str]:
    return set(values)


POWER_USB = refs("R101", "R102", "R103", "C101", "F1", "D101", "U16")
POWER_PROTECTION = refs(
    "R104", "C102", "R105", "R106", "R107", "TP101", "TP102", "TP103", "TP104"
)
POWER_CHARGER = refs(
    "R108", "R109", "R110", "R111", "R112", "R113", "R114", "R115", "R126", "R128",
    "C103", "C104", "C105", "C106", "C121", "C122",
)
POWER_BUCK = refs(
    "R116", "R117", "R118", "R119", "C107", "C108", "C109", "C110", "C111", "C112",
    "C123", "C124",
)
POWER_BOOST = refs(
    "R120", "R121", "R122", "C113", "C114", "C115", "C116"
)
POWER_AUX = refs("R123", "R124", "R127", "C117", "C118", "C119")
POWER_GAUGE = refs("R125", "C120")

SD_REFS = refs(
    "R510", "R511", "R512", "R513", "R514", "R515", "R516", "R517", "R518", "R519",
    "C510", "C511",
)
EXPANSION_REFS = {f"R{number}" for number in range(710, 735)}
POWER_TESTPOINTS = {f"TP{number}" for number in range(101, 111)}


def region_plan(part: dict[str, object]) -> Sequence[Region]:
    reference = str(part["reference"])
    block = str(part["block"])

    if reference in POWER_TESTPOINTS:
        return (
            LOWER_FRONT_LEFT,
            LOWER_FRONT_RIGHT,
            TOP_FRONT_STRIP,
            MCU_FRONT_BOTTOM,
        )
    if reference in POWER_USB:
        return (POWER_RIGHT_BACK, POWER_MID_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if reference in POWER_PROTECTION:
        return (POWER_RIGHT_BACK, POWER_MID_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if reference in POWER_CHARGER:
        return (POWER_RIGHT_BACK, POWER_MID_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if reference in POWER_BUCK:
        return (POWER_BUCK_BACK, POWER_MID_BACK, POWER_RIGHT_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if reference in POWER_BOOST:
        return (POWER_BOOST_BACK, POWER_MID_BACK, POWER_RIGHT_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if reference in POWER_AUX or reference in POWER_GAUGE:
        return (POWER_RIGHT_BACK, POWER_MID_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if block.startswith("01 "):
        return (POWER_RIGHT_BACK, POWER_MID_BACK, BACK_UNDER_ESP_BODY, SD_BACK, TOP_BACK_STRIP)
    if block.startswith("02 "):
        return (
            MCU_FRONT_SIDE,
            MCU_FRONT_BOTTOM,
            NFC_FRONT,
            LOWER_FRONT_LEFT,
            TOP_FRONT_STRIP,
            BACK_UNDER_ESP_BODY,
        )
    if block.startswith("03 "):
        return (NFC_FRONT, MCU_FRONT_BOTTOM, GNSS_FRONT, LOWER_FRONT_RIGHT)
    if block.startswith("04 "):
        return (SUBGHZ_BACK, POWER_BOOST_BACK, MCU_FRONT_BOTTOM, LOWER_FRONT_RIGHT)
    if block.startswith("05 ") and reference in SD_REFS:
        return (SD_BACK, LOWER_FRONT_LEFT)
    if block.startswith("05 "):
        return (LOWER_FRONT_LEFT, SD_BACK, GNSS_FRONT, NFC_FRONT)
    if block.startswith("06 "):
        return (
            LOWER_FRONT_LEFT,
            LOWER_FRONT_RIGHT,
            NFC_FRONT,
            SD_BACK,
            RIGHT_BACK_TOP,
            BACK_UNDER_ESP_BODY,
            POWER_RIGHT_BACK,
            TOP_FRONT_STRIP,
            TOP_BACK_STRIP,
        )
    if block.startswith("07 ") and reference in EXPANSION_REFS:
        return (
            LOWER_FRONT_LEFT,
            LOWER_FRONT_RIGHT,
            SD_BACK,
            TOP_FRONT_STRIP,
            TOP_BACK_STRIP,
        )
    if block.startswith("07 "):
        return (RIGHT_BACK_TOP, SD_BACK, POWER_MID_BACK, POWER_RIGHT_BACK)
    raise RuntimeError(f"No placement region plan for {reference} ({block})")


def footprint_area(footprint: pcbnew.FOOTPRINT) -> float:
    configure_side_and_rotation(footprint, "F", 0.0)
    box = courtyard_box(footprint, "F")
    return box.width * box.height


def placement_priority(part: dict[str, object]) -> int:
    """Pack the small, topology-constrained RF/edge regions before power."""
    block = str(part["block"])
    if block.startswith("04 "):
        return 0
    if block.startswith("05 "):
        return 1
    if block.startswith("03 "):
        return 2
    if block.startswith("02 "):
        return 3
    if block.startswith("07 ") and str(part["reference"]) in EXPANSION_REFS:
        return 4
    if block.startswith("07 "):
        return 5
    if block.startswith("01 "):
        return 6
    if block.startswith("06 "):
        return 7
    return 8


def add_rect(board: pcbnew.BOARD, box: Box, layer: int, width_mm: float = 0.18) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_RECT)
    shape.SetStart(vec_mm(box.left, box.top))
    shape.SetEnd(vec_mm(box.right, box.bottom))
    shape.SetLayer(layer)
    shape.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(shape)


def add_text(
    board: pcbnew.BOARD,
    value: str,
    x_mm: float,
    y_mm: float,
    layer: int,
    size_mm: float = 0.75,
) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(value)
    item.SetPosition(vec_mm(x_mm, y_mm))
    item.SetLayer(layer)
    item.SetTextSize(vec_mm(size_mm, size_mm))
    item.SetTextThickness(pcbnew.FromMM(max(0.1, size_mm * 0.14)))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    board.Add(item)


def add_placement_guides(board: pcbnew.BOARD) -> None:
    add_rect(board, NFC_OUTER, pcbnew.Dwgs_User)
    add_text(board, "AE1 FULL COMPONENT KEEPOUT - BOTH SIDES", 40.9, 51.4, pcbnew.Cmts_User)
    add_rect(board, ESP_ANTENNA, pcbnew.Dwgs_User)
    add_text(board, "ESP32 ANTENNA KEEPOUT", 93.0, 27.4, pcbnew.Cmts_User, 0.65)
    add_text(
        board,
        "NETLISTED PLACEMENT ONLY - UNROUTED / NOT FOR PRODUCTION",
        70.5,
        72.7,
        pcbnew.Cmts_User,
        0.72,
    )
    # JST-PH cable polarity is not standardized.  Keep the board-defined
    # polarity visible even after the connector is fitted, on silk and fab.
    for layer in (pcbnew.F_SilkS, pcbnew.F_Fab):
        add_text(board, "BAT -", 96.0, 63.6, layer, 0.78)
        add_text(board, "BAT +", 96.0, 67.4, layer, 0.78)


def remove_template_caption(board: pcbnew.BOARD) -> None:
    for drawing in list(board.GetDrawings()):
        if isinstance(drawing, pcbnew.PCB_TEXT) and "MECHANICAL SCAFFOLD" in drawing.GetText():
            board.Remove(drawing)


def validate_round_trip(
    output: Path,
    expected_parts: Sequence[dict[str, object]],
    expected_net_names: set[str],
) -> None:
    board = pcbnew.LoadBoard(str(output))
    footprints = list(board.GetFootprints())
    actual_refs = {footprint.GetReference() for footprint in footprints}
    expected_refs = {str(part["reference"]) for part in expected_parts}
    if actual_refs != expected_refs:
        missing = sorted(expected_refs - actual_refs, key=natural_key)
        extra = sorted(actual_refs - expected_refs, key=natural_key)
        raise RuntimeError(f"Round-trip reference mismatch; missing={missing}, extra={extra}")

    actual_nets = {
        pad.GetNetname()
        for footprint in footprints
        for pad in footprint.Pads()
        if pad.GetNetname()
    }
    if actual_nets != expected_net_names:
        raise RuntimeError(
            "Round-trip net mismatch; missing="
            + repr(sorted(expected_net_names - actual_nets))
            + ", extra="
            + repr(sorted(actual_nets - expected_net_names))
        )

    expected_assignments = {
        (
            str(part["reference"]),
            str(pin),
            pin_board_net_name(part, pin, net_name),
        )
        for part in expected_parts
        for pin, net_name in dict(part["pins"]).items()
    }
    actual_assignments = {
        (footprint.GetReference(), pad.GetNumber(), pad.GetNetname())
        for footprint in footprints
        for pad in footprint.Pads()
        if pad.GetNumber() and pad.GetNetname()
    }
    missing_assignments = expected_assignments - actual_assignments
    if missing_assignments:
        sample = sorted(missing_assignments, key=lambda row: (natural_key(row[0]), natural_key(row[1])))[:12]
        raise RuntimeError(f"Round-trip lost pad/net assignments, first entries: {sample}")

    actual_by_ref = {footprint.GetReference(): footprint for footprint in footprints}
    metadata_mismatches: list[str] = []
    for part in expected_parts:
        reference = str(part["reference"])
        footprint = actual_by_ref[reference]
        fields = {
            str(name): str(value)
            for name, value in dict(part.get("fields", {})).items()
        }
        expected_dnp = bool(
            part.get("dnp", field_is_true(fields.get("DNP", "")))
        )
        expected_in_bom = bool(part.get("in_bom", True))
        if bool(footprint.IsDNP()) != expected_dnp:
            metadata_mismatches.append(f"{reference}:DNP")
        if bool(footprint.IsExcludedFromBOM()) == expected_in_bom:
            metadata_mismatches.append(f"{reference}:in_bom")
        for field_name, field_value in fields.items():
            if not footprint.HasField(field_name):
                metadata_mismatches.append(f"{reference}:missing {field_name}")
            elif footprint.GetFieldText(field_name) != field_value:
                metadata_mismatches.append(f"{reference}:{field_name}")
    if metadata_mismatches:
        raise RuntimeError(
            "Round-trip footprint metadata mismatch, first entries: "
            + ", ".join(metadata_mismatches[:12])
        )


def validate_serialized_stackup(output: Path) -> None:
    serialized = output.read_text(encoding="utf-8")
    required_fragments = (
        "(stackup",
        '(layer "F.Cu"',
        '(layer "In1.Cu"',
        '(layer "In2.Cu"',
        '(layer "B.Cu"',
        "(thickness 0.035)",
        "(thickness 0.0152)",
        "(thickness 0.2104)",
        "(thickness 1.065)",
        '(material "7628")',
        "(epsilon_r 4.4)",
        '(copper_finish "ENIG")',
        '(4 "In1.Cu" power "GND")',
        '(6 "In2.Cu" power "PWR")',
    )
    missing = [fragment for fragment in required_fragments if fragment not in serialized]
    if missing:
        raise RuntimeError("Serialized JLC04161H-7628 stackup is incomplete: " + repr(missing))


def main() -> int:
    parser = argparse.ArgumentParser()
    hardware_dir = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--design",
        type=Path,
        default=hardware_dir / "design-netlist.json",
        help="JSON emitted by generate_schematic.py",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=hardware_dir / "templates" / "PocketLab-Card-mechanical.kicad_pcb",
        help="empty PCB containing the exact mechanical outline",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=hardware_dir / "PocketLab-Card-netlisted.kicad_pcb",
        help="staging PCB output; the main board is protected",
    )
    args = parser.parse_args()

    design_path = args.design.resolve()
    template_path = args.template.resolve()
    output_path = args.output.resolve()
    protected_main = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if output_path == protected_main:
        raise RuntimeError("Refusing to overwrite hardware/PocketLab-Card.kicad_pcb")

    all_parts = load_design(design_path)
    populated_parts = [part for part in all_parts if str(part.get("footprint", ""))]
    if len(all_parts) != 241 or len(populated_parts) != 234:
        raise RuntimeError(
            f"Design count changed: expected 241 symbols / 234 footprints, got "
            f"{len(all_parts)} / {len(populated_parts)}. Review placement assumptions first."
        )

    board = pcbnew.LoadBoard(str(template_path))
    if list(board.GetFootprints()):
        raise RuntimeError("Mechanical template is not empty")
    # KiCad 10.0.5's bundled SWIG bindings intermittently expose the title
    # block as a raw pointer when a board is loaded from a resolved Path.  The
    # mechanical template already carries the authoritative card title, so we
    # leave that metadata intact and place the staging warning on Cmts.User.

    nets = create_nets(board, populated_parts)
    footprints: dict[str, pcbnew.FOOTPRINT] = {}
    parts_by_ref = {str(part["reference"]): part for part in populated_parts}
    for part in populated_parts:
        footprint = load_footprint(hardware_dir, part)
        validate_footprint_pads(part, footprint)
        assign_pad_nets(part, footprint, nets)
        footprints[str(part["reference"])] = footprint

    # BOARD.Remove invalidates KiCad's short-lived PCB_IO plug-in wrapper in
    # 10.0.5, so template drawings are removed only after every library
    # footprint has been loaded.
    remove_template_caption(board)
    # FOOTPRINT.Flip dereferences the parent board in KiCad 10.0.5.  Attach
    # every loaded footprint before any back-side placement to avoid a native
    # access violation in the SWIG binding.
    for footprint in footprints.values():
        board.Add(footprint)

    fixed_by_ref = {placement.reference: placement for placement in FIXED_PLACEMENTS}
    unknown_fixed = sorted(set(fixed_by_ref) - set(footprints), key=natural_key)
    if unknown_fixed:
        raise RuntimeError("Fixed placement references missing from design: " + ", ".join(unknown_fixed))

    occupied: list[Occupied] = []
    # Keep the RF antenna volume clear on the back even before U1 is registered.
    occupied.append(Occupied("U1 ANTENNA KEEPOUT", "B", ESP_ANTENNA))

    for placement in FIXED_PLACEMENTS:
        footprint = footprints[placement.reference]
        place_fixed(footprint, placement, occupied)

    remaining = [
        part for part in populated_parts if str(part["reference"]) not in fixed_by_ref
    ]
    remaining.sort(
        key=lambda part: (
            placement_priority(part),
            -footprint_area(footprints[str(part["reference"])]),
            natural_key(str(part["reference"])),
        )
    )
    side_counts = {"F": 0, "B": 0}
    side_counts.update(
        {
            side: sum(1 for placement in FIXED_PLACEMENTS if placement.side == side)
            for side in ("F", "B")
        }
    )
    for part in remaining:
        reference = str(part["reference"])
        footprint = footprints[reference]
        side, _ = place_in_regions(footprint, reference, region_plan(part), occupied)
        side_counts[side] += 1

    add_placement_guides(board)
    title_block = board.GetTitleBlock()
    title_block.SetRevision("PROTOTYPE")
    title_block.SetComment(2, "UNROUTED netlisted placement; not for production")
    board.SetTitleBlock(title_block)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    # Give KiCad/CLI the same netclasses and custom-rule context as the main
    # project without touching the main PCB itself.
    project_source = hardware_dir / "PocketLab-Card.kicad_pro"
    project_output = output_path.with_suffix(".kicad_pro")
    if project_source.resolve() != project_output.resolve():
        shutil.copyfile(project_source, project_output)
    rules_source = hardware_dir / "PocketLab-Card.kicad_dru"
    if rules_source.exists():
        shutil.copyfile(rules_source, output_path.with_suffix(".kicad_dru"))

    expected_nets = {
        pin_board_net_name(part, pin, net_name)
        for part in populated_parts
        for pin, net_name in dict(part["pins"]).items()
    }
    validate_round_trip(output_path, populated_parts, expected_nets)
    validate_serialized_stackup(output_path)

    print(f"Saved netlisted placement: {output_path}")
    print(
        f"Symbols: {len(all_parts)}; populated footprints: {len(populated_parts)} "
        f"(front {side_counts['F']}, back {side_counts['B']}); nets: {len(expected_nets)}"
    )
    print("Pad audit: no schematic pin is missing; only J1 A8/B8 and J4 MP are allowed extras")
    print("Stackup audit: JLC04161H-7628 / ENIG serialized; L2=GND and L3=PWR")
    print("Placement audit: no unapproved AABB courtyard, full NFC-keepout or board-inset collision")
    print("Known edge exceptions: U1, J1, J3, J4, J5, D1 and U13 are intentional")
    print("Routing was not generated; run KiCad DRC and RF/power review before using this board")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
