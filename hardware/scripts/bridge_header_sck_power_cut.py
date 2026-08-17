"""Bridge the single +5V_RAW plane slot made by the reviewed SCK route."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


F_PATH = (
    (75.5000, 61.5000),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def connected(board: pcbnew.BOARD, first: pcbnew.BOARD_ITEM, second: pcbnew.BOARD_ITEM) -> bool:
    board.BuildConnectivity()
    wanted = item_key(second)
    return any(
        item_key(candidate) == wanted
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def add_via(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    position: tuple[float, float],
) -> pcbnew.PCB_VIA:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(position))
    via.SetWidth(pcbnew.FromMM(0.45))
    via.SetDrill(pcbnew.FromMM(0.20))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    via.SetLocked(True)
    board.Add(via)
    return via


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
    net = board.FindNet("/+5V_RAW")
    if net is None:
        raise RuntimeError("Missing /+5V_RAW")
    existing = [
        item
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA)
        and item.GetNetname() == "/+5V_RAW"
        and item.GetPosition() == point(F_PATH[0])
    ]
    if len(existing) > 1:
        raise RuntimeError("Multiple +5V_RAW stitch vias already exist")
    if not existing:
        add_via(board, net, F_PATH[0])
    for start, end in zip(F_PATH, F_PATH[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(start))
        track.SetEnd(point(end))
        track.SetWidth(pcbnew.FromMM(0.20))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    reloaded_vias = [
        item
        for item in reloaded.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA)
        and item.GetNetname() == "/+5V_RAW"
        and item.GetPosition() == point(F_PATH[0])
    ]
    if len(reloaded_vias) != 1 or not connected(
        reloaded, reloaded_vias[0], pad(reloaded, "C607", "1")
    ):
        raise RuntimeError("Saved +5V_RAW bridge does not reach the existing power tree")
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"Saved +5V_RAW bridge candidate: {output_path}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
