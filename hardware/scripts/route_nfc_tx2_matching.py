"""Route the short PN532 TX2 matching branch without adding a via.

The only outer-layer corridor between L302.2 and C309.1 passes below C301
and above the reviewed LF_DIN_5V crossing.  Its centreline is fixed at
34.075 mm so the 0.15-mm NFC trace retains 0.25 mm to both neighbours.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


NET = "/NFC_TX2_F"
ROUTE = (
    (65.0000, 35.9375),
    (64.7500, 35.6875),
    (64.7500, 34.2000),
    (64.9500, 34.0750),
    (66.2500, 34.0750),
    (67.2250, 33.0000),
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def connected(board: pcbnew.BOARD, first: pcbnew.PAD, second: pcbnew.PAD) -> bool:
    board.BuildConnectivity()
    second_key = item_key(second)
    return any(
        item_key(candidate) == second_key
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(0.15))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


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
    source = pad(board, "L302", "2")
    target = pad(board, "C309", "1")
    if source.GetNetname() != NET or target.GetNetname() != NET:
        raise RuntimeError("NFC TX2 matching endpoint assignment changed")

    added = 0
    if not connected(board, source, target):
        net = board.FindNet(NET)
        if net is None:
            raise RuntimeError(f"Missing PCB net: {NET}")
        for start, end in zip(ROUTE, ROUTE[1:]):
            add_track(board, net, start, end)
            added += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "L302", "2"), pad(reloaded, "C309", "1")):
        raise RuntimeError("L302.2 is still disconnected from C309.1")
    print(f"Saved NFC TX2 matching candidate: {output_path}; tracks={added}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
