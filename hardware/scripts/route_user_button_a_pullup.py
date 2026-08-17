"""Join the UP button contact to its local 3.3-V pull-up resistor.

The reviewed path leaves the right-hand SW3.1 contact on F.Cu, uses a short
ordinary-signal corridor on In2.Cu between the dense LF/RGB fanouts, and
returns to B.Cu at R608.1.  Zone refill is mandatory because the route crosses
the PWR plane; In1.Cu remains reserved for GND.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


NET_NAME = "/USER_BUTTON_A_N"
FRONT_ROUTE = (
    (53.0500, 54.3500),
    (52.0500, 55.6000),
)
FIRST_VIA = FRONT_ROUTE[-1]
POWER_LAYER_ROUTE = (
    FIRST_VIA,
    (54.5500, 57.6000),
    (54.9000, 57.6000),
    (56.1000, 57.1000),
    (56.5500, 57.1000),
    (60.1000, 57.6000),
)
SECOND_VIA = POWER_LAYER_ROUTE[-1]
BACK_ROUTE = (
    SECOND_VIA,
    (60.0500, 58.6000),
    (58.4000, 60.3500),
    (55.8000, 60.1000),
    (55.2500, 59.8250),
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def pad_at(
    board: pcbnew.BOARD,
    reference: str,
    number: str,
    position: tuple[float, float],
) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    target = point(*position)
    matches = [
        candidate
        for candidate in footprint.Pads()
        if candidate.GetNumber() == number and candidate.GetPosition() == target
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {reference}.{number} pad at {position}, got {len(matches)}"
        )
    return matches[0]


def connected(board: pcbnew.BOARD, first: pcbnew.PAD, second: pcbnew.PAD) -> bool:
    board.BuildConnectivity()
    second_key = item_key(second)
    return any(
        item_key(candidate) == second_key
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def add_route(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    route: tuple[tuple[float, float], ...],
) -> int:
    for start, end in zip(route, route[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(0.15))
        track.SetLayer(layer)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)
    return len(route) - 1


def add_via(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    position: tuple[float, float],
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(*position))
    via.SetWidth(pcbnew.FromMM(0.45))
    via.SetDrill(pcbnew.FromMM(0.20))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    via.SetLocked(True)
    board.Add(via)


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
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    switch = pad_at(board, "SW3", "1", FRONT_ROUTE[0])
    pull_up = pad_at(board, "R608", "1", BACK_ROUTE[-1])
    if switch.GetNetname() != NET_NAME or pull_up.GetNetname() != NET_NAME:
        raise RuntimeError("UP-button endpoint assignment changed")

    added_tracks = 0
    added_vias = 0
    if not connected(board, switch, pull_up):
        net = board.FindNet(NET_NAME)
        if net is None:
            raise RuntimeError(f"Required net is missing: {NET_NAME}")
        added_tracks += add_route(board, net, pcbnew.F_Cu, FRONT_ROUTE)
        add_via(board, net, FIRST_VIA)
        added_vias += 1
        added_tracks += add_route(board, net, pcbnew.In2_Cu, POWER_LAYER_ROUTE)
        add_via(board, net, SECOND_VIA)
        added_vias += 1
        added_tracks += add_route(board, net, pcbnew.B_Cu, BACK_ROUTE)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    reloaded_switch = pad_at(reloaded, "SW3", "1", FRONT_ROUTE[0])
    reloaded_pull_up = pad_at(reloaded, "R608", "1", BACK_ROUTE[-1])
    if not connected(reloaded, reloaded_switch, reloaded_pull_up):
        raise RuntimeError("SW3.1 is still disconnected from R608.1")

    print(
        f"Saved UP-button pull-up candidate: {output_path}; "
        f"tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
