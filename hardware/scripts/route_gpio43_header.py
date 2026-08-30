"""Join the protected GPIO43 output to expansion-header pad J5.11.

Only a named candidate is written.  The short route uses the PWR signal layer
(``In2.Cu``); the dedicated ``In1.Cu`` GND plane remains untouched.  J5.11 is
a through-hole pad, so a single small tented via in the R718.2 land is enough
for the layer transition.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


NET_NAME = "/GPIO43"
ROUTE = (
    (43.0500, 64.2250),
    (44.2350, 63.1900),
    (58.5400, 63.1900),
    (59.8100, 64.4600),
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


def add_route(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM) -> int:
    for start, end in zip(ROUTE, ROUTE[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(0.15))
        track.SetLayer(pcbnew.In2_Cu)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)
    return len(ROUTE) - 1


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(*ROUTE[0]))
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
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    board = pcbnew.LoadBoard(str(input_path))
    source = pad(board, "R718", "2")
    header = pad(board, "J5", "11")
    if source.GetNetname() != NET_NAME or header.GetNetname() != NET_NAME:
        raise RuntimeError("GPIO43 endpoint assignment changed")

    added_tracks = 0
    added_vias = 0
    if not connected(board, source, header):
        net = board.FindNet(NET_NAME)
        if net is None:
            raise RuntimeError(f"Required net is missing: {NET_NAME}")
        add_via(board, net)
        added_vias = 1
        added_tracks = add_route(board, net)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "R718", "2"), pad(reloaded, "J5", "11")):
        raise RuntimeError("R718.2 is still disconnected from J5.11")

    print(
        f"Saved GPIO43 header candidate: {output_path}; "
        f"tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
