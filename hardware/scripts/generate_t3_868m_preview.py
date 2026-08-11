"""Generate the project-local KiCad VRML preview for the T3-868M antenna.

KiCad's WRL importer is most reliable with explicit primitive geometry.  The
model therefore approximates the 868-MHz helical spring with short, tangent
box segments rather than an Extrusion node.  It is an assembly preview only;
the manufacturer drawing and the PCB footprint remain authoritative.

Run with any Python 3 interpreter::

    python hardware/scripts/generate_t3_868m_preview.py
"""

from __future__ import annotations

import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "PocketLab_Custom.3dshapes" / "T3-868M_preview.wrl"

# KiCad interprets VRML coordinates in 0.1-inch units.  The finished preview
# is approximately 17 x 5.5 mm, with its feed end next to footprint pad 1.
FREE_X = -7.48
FEED_X = -0.95
RADIUS = 1.02
CENTRE_Z = 1.11
WIRE = 0.22
TURNS = 7
SEGMENTS_PER_TURN = 12
PHASE = -math.pi / 2.0


def point(index: int, segment_count: int) -> tuple[float, float, float]:
    fraction = index / segment_count
    angle = PHASE - 2.0 * math.pi * TURNS * fraction
    x = FREE_X + (FEED_X - FREE_X) * fraction
    y = RADIUS * math.cos(angle)
    z = CENTRE_Z + RADIUS * math.sin(angle)
    return x, y, z


def box_segment(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    width: float = WIRE,
) -> str:
    dx, dy, dz = (end[i] - start[i] for i in range(3))
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    ux, uy, uz = dx / length, dy / length, dz / length

    # Rotate the Box local X axis onto the segment direction.  The rotation
    # axis is cross((1, 0, 0), direction).
    axis_x, axis_y, axis_z = 0.0, -uz, uy
    axis_length = math.hypot(axis_y, axis_z)
    if axis_length < 1e-9:
        axis_x, axis_y, axis_z, angle = 0.0, 0.0, 1.0, 0.0
    else:
        axis_y /= axis_length
        axis_z /= axis_length
        angle = math.acos(max(-1.0, min(1.0, ux)))

    midpoint = tuple((start[i] + end[i]) / 2.0 for i in range(3))
    return f"""Transform {{
  translation {midpoint[0]:.5f} {midpoint[1]:.5f} {midpoint[2]:.5f}
  rotation {axis_x:.5f} {axis_y:.5f} {axis_z:.5f} {angle:.5f}
  children [ Shape {{ appearance USE Copper geometry Box {{ size {length:.5f} {width:.5f} {width:.5f} }} }} ]
}}"""


def main() -> None:
    segment_count = TURNS * SEGMENTS_PER_TURN
    segments = [
        box_segment(point(index, segment_count), point(index + 1, segment_count))
        for index in range(segment_count)
    ]

    # A short straight stem joins the helical winding to the footprint's only
    # electrical pad.  The opposite end deliberately remains electrically open.
    feed = point(segment_count, segment_count)
    segments.append(box_segment(feed, (0.0, 0.0, 0.09)))

    anchor = """Transform {
  # Small nonconductive adhesive bridge at the free end; assembly aid only.
  translation -7.24500 -1.11000 1.11000
  children [ Shape { appearance USE Anchor geometry Box { size 0.55000 0.30000 0.45000 } } ]
}
"""

    header = """#VRML V2.0 utf8
# Mechanical preview only; manufacturer data and footprint are authoritative.
# Explicit tangent boxes approximate a 17 x 5.5 mm cylindrical helical spring.
DEF Copper Appearance {
  material Material {
    diffuseColor 0.72 0.42 0.08
    specularColor 0.95 0.72 0.25
    shininess 0.72
  }
}
DEF Anchor Appearance {
  material Material {
    diffuseColor 0.30 0.34 0.38
    specularColor 0.08 0.08 0.08
    transparency 0.25
  }
}
"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(header + "\n".join(segments) + "\n" + anchor, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(segments)} segments)")


if __name__ == "__main__":
    main()
