"""Build a reviewed J5.25-to-SCK-tree candidate through the header neck."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


B_PATH = (
    (49.6500, 72.0800),
    (50.9000, 70.8300),
    (53.4000, 70.8300),
    (53.5250, 70.7050),
    (53.5250, 68.3300),
    (53.6500, 68.2050),
    (56.0250, 68.2050),
    (56.0250, 67.5800),
    (56.0000, 67.0000),
    (56.0000, 65.7500),
    (58.5000, 65.7500),
    (58.5000, 60.7500),
    (59.2500, 60.5000),
    (63.5000, 60.5000),
)

IN2_PATH = (
    (63.5000, 60.5000),
    (69.0000, 60.5000),
    (69.8750, 61.3750),
    (73.1250, 61.3750),
    (73.2500, 61.5000),
    (73.3750, 61.5000),
    (73.5000, 61.6250),
    (73.6250, 61.6250),
    (73.7500, 61.7500),
    (73.8750, 61.7500),
    (74.0000, 61.8750),
    (74.1250, 61.8750),
    (74.2500, 62.0000),
    (74.5000, 62.0000),
    (74.6250, 62.1250),
    (74.7500, 62.1250),
    (74.8750, 62.2500),
    (75.0000, 62.2500),
    (75.1250, 62.3750),
    (75.2500, 62.3750),
    (75.3750, 62.5000),
    (76.7500, 62.5000),
    (76.8750, 62.6250),
    (77.0000, 62.6250),
    (78.1250, 63.7500),
    (78.2500, 63.7500),
    (78.3750, 63.8750),
    (78.6250, 63.8750),
    (78.7500, 64.0000),
    (78.8750, 64.0000),
    (79.0000, 64.1250),
    (79.7500, 64.1250),
    (80.2500, 64.6750),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def connected(board: pcbnew.BOARD, first: pcbnew.BOARD_ITEM, second: pcbnew.BOARD_ITEM) -> bool:
    board.BuildConnectivity()
    wanted = item_key(second)
    return any(
        item_key(candidate) == wanted
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def add_path(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    positions: tuple[tuple[float, float], ...],
) -> None:
    for start, end in zip(positions, positions[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(start))
        track.SetEnd(point(end))
        track.SetWidth(pcbnew.FromMM(0.20))
        track.SetLayer(layer)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point((63.5, 60.5)))
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

    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    net = board.FindNet("/SPI_SCK_HDR")
    if net is None:
        raise RuntimeError("Missing /SPI_SCK_HDR")
    already_connected = connected(board, pad(board, "J5", "25"), pad(board, "R732", "2"))
    if not already_connected:
        add_path(board, net, pcbnew.B_Cu, B_PATH)
        add_via(board, net)
        add_path(board, net, pcbnew.In2_Cu, IN2_PATH)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "J5", "25"), pad(reloaded, "R732", "2")):
        raise RuntimeError("Saved SCK bridge is not connected end to end")
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"Saved SCK bridge candidate: {output_path}; "
        f"added={not already_connected}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
