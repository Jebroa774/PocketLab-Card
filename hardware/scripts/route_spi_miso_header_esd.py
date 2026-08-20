"""Join the protected SPI-MISO header branch to its ESD-array channel.

U25.1 is bottom-side copper and R734.2 is top-side copper.  An offset through
via within U25.1 and a short F.Cu escape from R734.2 connect a locked 0.15-mm
route on In2.Cu while the dedicated In1.Cu ground plane remains untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


NET_NAME = "/SPI_MISO_HDR"
ESD_VIA = (82.0000, 59.2000)
RESISTOR_PAD = (89.8500, 65.5750)
RESISTOR_VIA = (92.1500, 66.7500)
RESISTOR_ESCAPE = (
    RESISTOR_PAD,
    (89.8500, 66.4000),
    (91.3000, 66.4000),
    RESISTOR_VIA,
)
ROUTE = (
    ESD_VIA,
    (82.5000, 58.8500),
    (84.3000, 58.8500),
    (85.1000, 59.6500),
    (85.1000, 61.4000),
    (86.0000, 62.8000),
    (88.0000, 63.8000),
    (89.2500, 65.0000),
    RESISTOR_VIA,
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
    track.SetLayer(pcbnew.In2_Cu)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


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
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    esd = pad(board, "U25", "1")
    resistor = pad(board, "R734", "2")
    if esd.GetNetname() != NET_NAME or resistor.GetNetname() != NET_NAME:
        raise RuntimeError("SPI-MISO header endpoint assignment changed")

    added_tracks = 0
    added_vias = 0
    if not connected(board, esd, resistor):
        net = board.FindNet(NET_NAME)
        if net is None:
            raise RuntimeError(f"Missing PCB net: {NET_NAME}")
        add_via(board, net, ESD_VIA)
        add_via(board, net, RESISTOR_VIA)
        added_vias = 2
        for start, end in zip(ROUTE, ROUTE[1:]):
            add_track(board, net, start, end)
            added_tracks += 1
        for start, end in zip(RESISTOR_ESCAPE, RESISTOR_ESCAPE[1:]):
            escape = pcbnew.PCB_TRACK(board)
            escape.SetStart(point(*start))
            escape.SetEnd(point(*end))
            escape.SetWidth(pcbnew.FromMM(0.15))
            escape.SetLayer(pcbnew.F_Cu)
            escape.SetNet(net)
            escape.SetLocked(True)
            board.Add(escape)
            added_tracks += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "U25", "1"), pad(reloaded, "R734", "2")):
        raise RuntimeError("U25.1 is still disconnected from R734.2")
    print(
        f"Saved SPI-MISO header candidate: {output_path}; "
        f"tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
