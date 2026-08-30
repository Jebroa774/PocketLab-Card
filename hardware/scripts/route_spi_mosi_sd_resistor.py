"""Join the SD-card MOSI series resistor to the shared SPI-MOSI trunk.

The reviewed path starts at the existing U1/R129 SPI-MOSI through-via,
crosses the dense USB/charger field on L3/PWR, and returns to F.Cu beside
R511.1.  L2/GND remains plane-only and the filled L3 power zones are restored
before the candidate is saved.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


NET_NAME = "/SPI_MOSI"
POWER_LAYER_ROUTE = (
    (85.9450, 44.0000),
    (85.5500, 44.8000),
    (85.5500, 50.4000),
    (86.2000, 51.2000),
    (86.2000, 53.4000),
    (88.4000, 53.4000),
    (88.4000, 53.0000),
)
SIGNAL_VIA = POWER_LAYER_ROUTE[-1]
FRONT_ROUTE = (
    (88.0625, 51.4000),
    SIGNAL_VIA,
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
    trunk = pad(board, "R129", "2")
    sd_resistor = pad(board, "R511", "1")
    if trunk.GetNetname() != NET_NAME or sd_resistor.GetNetname() != NET_NAME:
        raise RuntimeError("SPI-MOSI endpoint assignment changed")

    added_tracks = 0
    added_vias = 0
    if not connected(board, trunk, sd_resistor):
        net = board.FindNet(NET_NAME)
        if net is None:
            raise RuntimeError(f"Required net is missing: {NET_NAME}")
        added_tracks += add_route(board, net, pcbnew.In2_Cu, POWER_LAYER_ROUTE)
        add_via(board, net, SIGNAL_VIA)
        added_vias += 1
        added_tracks += add_route(board, net, pcbnew.F_Cu, FRONT_ROUTE)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "R129", "2"), pad(reloaded, "R511", "1")):
        raise RuntimeError("R511.1 is still disconnected from the shared SPI-MOSI trunk")

    print(
        f"Saved SD SPI-MOSI candidate: {output_path}; "
        f"tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
