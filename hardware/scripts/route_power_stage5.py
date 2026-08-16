"""Route VSYS through a hand-friendly SPI crossover corridor.

The accepted outer-layer placement leaves the charger VSYS output and the
shared SPI MOSI bus competing for one narrow B.Cu corridor.  This pass adds a
real 0805 zero-ohm series crossover (R129), moves the still-unrouted R122
pull-down out of the corridor, and completes the charger/U7 VSYS connection.

VSYS remains 0.80 mm on both sides of R129 and uses a 0.30-mm neck only for
the roughly 2.8-mm passage between its lands.  L2 GND and L3 +3V3 stay solid;
no signal or power trace is introduced on an inner layer.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew

import build_pcb
import route_lf_global as router


MAIN_SPI = "/SPI_MOSI"
JUMPER_SPI = "/SPI_MOSI_JMP"
VSYS = "/VSYS"
GND = "/GND"
JUMPER_REFERENCE = "R129"
RULE_AREA_NAME = "VSYS_SPI_CROSSOVER_NECK"


REMOVED_TRACKS: tuple[
    tuple[str, tuple[float, float], tuple[float, float]], ...
] = (
    (GND, (86.9, 49.55), (84.178273, 49.55)),
    (GND, (84.178273, 49.55), (81.555685, 52.172587)),
    (MAIN_SPI, (85.7125, 43.85), (85.7125, 47.35)),
    (MAIN_SPI, (85.7125, 47.35), (83.2125, 49.85)),
    (MAIN_SPI, (83.2125, 49.85), (82.2125, 49.85)),
    (GND, (83.0875, 51.1), (81.555685, 52.172587)),
)

GND_SEGMENTS = (
    ((90.6625, 44.5), (90.75, 43.75), 0.20),
    ((86.9, 49.55), (88.7625, 49.75), 0.20),
)

MAIN_SPI_SEGMENTS = (
    ((85.7125, 43.85), (85.7125, 47.35), 0.20),
    ((85.7125, 47.35), (84.2, 48.1875), 0.20),
)

JUMPER_SPI_SEGMENTS = (
    ((84.2, 50.0125), (83.0, 50.0125), 0.20),
    ((83.0, 50.0125), (82.8, 49.85), 0.20),
    ((82.8, 49.85), (82.2125, 49.85), 0.20),
)

VSYS_SEGMENTS = (
    ((89.95, 49.0625), (89.95, 48.3125), 0.20),
    ((90.45, 49.0625), (89.95, 48.5625), 0.20),
    ((89.95, 48.5625), (89.95, 48.3125), 0.20),
    ((89.95, 48.3125), (88.4, 48.3125), 0.20),
    ((88.4, 48.3125), (87.9, 48.3125), 0.50),
    ((87.9, 48.3125), (86.8, 47.75), 0.50),
    ((86.8, 47.75), (86.3, 48.25), 0.80),
    ((86.3, 48.25), (85.8, 48.25), 0.80),
    ((85.8, 48.25), (85.6, 48.45), 0.30),
    ((85.6, 48.45), (85.6, 49.1), 0.30),
    ((86.9, 51.45), (86.4, 50.95), 0.80),
    ((86.4, 50.95), (85.8, 50.95), 0.80),
    ((85.8, 50.95), (85.6, 50.75), 0.30),
    ((85.6, 50.75), (85.6, 49.1), 0.30),
    ((85.6, 49.1), (82.8, 49.1), 0.30),
    ((82.8, 49.1), (82.6, 48.9), 0.30),
    ((82.6, 48.9), (82.6, 48.1), 0.80),
    ((82.6, 48.1), (82.05, 47.5), 0.80),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def close(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return math.dist(first, second) < 0.002


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    return router.pad_by_reference(board, reference, number)


def get_or_add_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def remove_exact_track(
    board: pcbnew.BOARD,
    net_name: str,
    first: tuple[float, float],
    second: tuple[float, float],
) -> None:
    for item in list(board.GetTracks()):
        if isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != net_name:
            continue
        start = xy(item.GetStart())
        end = xy(item.GetEnd())
        if (close(start, first) and close(end, second)) or (
            close(start, second) and close(end, first)
        ):
            board.Delete(item)
            return
    raise RuntimeError(f"Expected {net_name} segment is missing: {first} -> {second}")


def remove_exact_via(
    board: pcbnew.BOARD, net_name: str, position: tuple[float, float]
) -> None:
    for item in list(board.GetTracks()):
        if not isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != net_name:
            continue
        if close(xy(item.GetPosition()), position):
            board.Delete(item)
            return
    raise RuntimeError(f"Expected {net_name} via is missing at {position}")


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(start))
    track.SetEnd(point(end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(pcbnew.B_Cu)
    track.SetNet(get_or_add_net(board, net_name))
    track.SetLocked(True)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    position: tuple[float, float],
    diameter_mm: float = 0.50,
    drill_mm: float = 0.30,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(position))
    via.SetWidth(pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(drill_mm))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(get_or_add_net(board, net_name))
    via.SetLocked(True)
    board.Add(via)


def add_rule_area(board: pcbnew.BOARD) -> None:
    if any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        raise RuntimeError(f"Input already contains {RULE_AREA_NAME}")
    area = pcbnew.ZONE(board)
    area.SetZoneName(RULE_AREA_NAME)
    area.SetLayer(pcbnew.B_Cu)
    area.SetIsRuleArea(True)
    area.SetDoNotAllowZoneFills(False)
    area.SetDoNotAllowTracks(False)
    area.SetDoNotAllowVias(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    outline = area.Outline()
    outline.NewOutline()
    for position in ((82.7, 48.0), (85.7, 48.0), (85.7, 51.0), (82.7, 51.0)):
        outline.Append(point(position))
    board.Add(area)


def add_jumper(board: pcbnew.BOARD) -> None:
    if board.FindFootprintByReference(JUMPER_REFERENCE) is not None:
        raise RuntimeError(f"Input already contains {JUMPER_REFERENCE}")
    library = build_pcb.footprint_root() / "Resistor_SMD.pretty"
    footprint = pcbnew.FootprintLoad(str(library), "R_0805_2012Metric")
    if footprint is None:
        raise RuntimeError(f"Cannot load R_0805_2012Metric from {library}")
    footprint.SetFPID(pcbnew.LIB_ID("Resistor_SMD", "R_0805_2012Metric"))
    footprint.SetReference(JUMPER_REFERENCE)
    footprint.SetValue("0R SPI CROSSOVER")
    footprint.SetFields(
        {
            "Manufacturer": "UNI-ROYAL",
            "MPN": "0805W8F0000T5E",
            "LCSC": "C17477",
        }
    )
    footprint.Value().SetVisible(False)
    for field_name in ("Manufacturer", "MPN", "LCSC"):
        footprint.GetField(field_name).SetVisible(False)
    footprint.SetPosition(point((84.2, 49.1)))
    board.Add(footprint)
    footprint.SetOrientationDegrees(90.0)
    footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    footprint.Reference().SetLayer(pcbnew.B_Fab)
    footprint.Reference().SetTextSize(point((0.8, 0.8)))
    footprint.Reference().SetTextThickness(pcbnew.FromMM(0.12))

    by_number = {item.GetNumber(): item for item in footprint.Pads()}
    by_number["2"].SetNet(get_or_add_net(board, MAIN_SPI))
    by_number["1"].SetNet(get_or_add_net(board, JUMPER_SPI))


def split_downstream_spi(board: pcbnew.BOARD) -> None:
    new_net = get_or_add_net(board, JUMPER_SPI)
    board.BuildConnectivity()
    seed = pad(board, "R402", "1")
    if seed.GetNetname() != MAIN_SPI:
        raise RuntimeError(f"R402.1 must start on {MAIN_SPI}, got {seed.GetNetname()}")
    connected = list(board.GetConnectivity().GetConnectedItems(seed))
    seed.SetNet(new_net)
    for item in connected:
        if hasattr(item, "SetNet"):
            item.SetNet(new_net)


def validate(board: pcbnew.BOARD) -> None:
    r129 = board.FindFootprintByReference(JUMPER_REFERENCE)
    r122 = board.FindFootprintByReference("R122")
    if r129 is None or r122 is None:
        raise RuntimeError("R122/R129 placement is missing")
    if not close(xy(r129.GetPosition()), (84.2, 49.1)) or abs(
        r129.GetOrientationDegrees() - 90.0
    ) > 0.01:
        raise RuntimeError("R129 placement changed")
    if not close(xy(r122.GetPosition()), (89.75, 44.5)) or abs(
        r122.GetOrientationDegrees()
    ) > 0.01:
        raise RuntimeError("R122 placement changed")
    if pad(board, JUMPER_REFERENCE, "2").GetNetname() != MAIN_SPI:
        raise RuntimeError("R129.2 must be SPI_MOSI")
    if pad(board, JUMPER_REFERENCE, "1").GetNetname() != JUMPER_SPI:
        raise RuntimeError("R129.1 must be SPI_MOSI_JMP")
    if pad(board, "R402", "1").GetNetname() != JUMPER_SPI:
        raise RuntimeError("R402.1 must be SPI_MOSI_JMP")

    for net_name, endpoints in (
        (MAIN_SPI, (("U21", "12"), (JUMPER_REFERENCE, "2"))),
        (JUMPER_SPI, ((JUMPER_REFERENCE, "1"), ("R402", "1"))),
        (
            VSYS,
            (
                ("U5", "10"),
                ("U5", "11"),
                ("C105", "1"),
                ("C122", "1"),
                ("C114", "1"),
                ("U7", "3"),
                ("L7", "1"),
            ),
        ),
    ):
        endpoint_pads = [pad(board, reference, number) for reference, number in endpoints]
        if any(item.GetNetname() != net_name for item in endpoint_pads):
            raise RuntimeError(f"{net_name} endpoint net mismatch")
        if any(
            not router.already_connected(board, endpoint_pads[0], item)
            for item in endpoint_pads[1:]
        ):
            raise RuntimeError(f"Serialized PCB lost {net_name} connectivity")

    board.BuildConnectivity()
    r122_ground = pad(board, "R122", "2")
    if not any(
        isinstance(item, pcbnew.PCB_TRACK)
        and close(xy(item.GetStart()), xy(r122_ground.GetPosition()))
        and close(xy(item.GetEnd()), (90.75, 43.75))
        for item in board.GetTracks()
    ):
        raise RuntimeError("R122 ground fanout track is missing")
    if not any(
        isinstance(item, pcbnew.PCB_VIA)
        and close(xy(item.GetPosition()), (90.75, 43.75))
        and item.GetNetname() == GND
        for item in board.GetTracks()
    ):
        raise RuntimeError("R122 ground fanout via is missing")
    if any(
        isinstance(item, pcbnew.PCB_VIA)
        and item.GetNetname() == GND
        and close(xy(item.GetPosition()), (81.555685, 52.172587))
        for item in board.GetTracks()
    ):
        raise RuntimeError("Obsolete orphan GND via remains")


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    for net_name, first, second in REMOVED_TRACKS:
        remove_exact_track(board, net_name, first, second)
    remove_exact_via(board, GND, (81.555685, 52.172587))

    r122 = board.FindFootprintByReference("R122")
    if r122 is None:
        raise RuntimeError("R122 is missing")
    r122.SetPosition(point((89.75, 44.5)))
    r122.SetOrientationDegrees(0.0)

    split_downstream_spi(board)
    add_jumper(board)
    add_rule_area(board)
    for start, end, width_mm in GND_SEGMENTS:
        add_track(board, GND, start, end, width_mm)
    add_via(board, GND, (90.75, 43.75))
    for start, end, width_mm in MAIN_SPI_SEGMENTS:
        add_track(board, MAIN_SPI, start, end, width_mm)
    for start, end, width_mm in JUMPER_SPI_SEGMENTS:
        add_track(board, JUMPER_SPI, start, end, width_mm)
    for start, end, width_mm in VSYS_SEGMENTS:
        add_track(board, VSYS, start, end, width_mm)

    validate(board)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    validate(pcbnew.LoadBoard(str(output_path)))
    print(
        "Added R129 0805 SPI crossover, moved R122 and completed the DRC-reviewed "
        "VSYS corridor"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
