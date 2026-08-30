"""Route the local U19-to-J2 microSD chip-select leg.

The former U19.2 ground escape occupied the only front-side approach to J2.2.
Move that escape toward the card edge while retaining its reviewed plane via,
then route CS into the socket pad through one local via.  Both plane layers
remain free of signal tracks.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


GND_NET = "/GND"
SIGNAL_NET = "/SD_CS_DEV"
REMOVE_GND_UUIDS = frozenset(
    {
        "1d0c3e2b-2314-486e-8a0d-7ab25a5193e9",
        "2f8efa93-3ff9-4167-8013-e0aaf6cbcbe7",
        "37d6e1b6-f856-44ac-9d30-def8f641cfc6",
        "4e7270bc-b904-440b-adad-cf0232c5a326",
        "6f418912-5a3e-406e-a6d3-81fcdce9086c",
        "baedf95f-3fa1-40b6-a395-e19d06ac6be4",
    }
)

GND_ROUTE = (
    (103.8500, 39.6375),
    (103.8500, 40.2500),
    (105.0000, 40.9500),
    (105.0000, 42.9000),
    (104.8500, 43.1375),
)
FRONT_ROUTE = (
    (102.9000, 39.6375),
    (102.5000, 39.6375),
    (102.5000, 40.8500),
    (103.9500, 40.8500),
    (104.4500, 41.2500),
)
SIGNAL_VIA = FRONT_ROUTE[-1]
BACK_ROUTE = (SIGNAL_VIA, (104.5500, 41.0050))


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
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


def add_route(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    route: tuple[tuple[float, float], ...],
    width_mm: float,
) -> int:
    for start, end in zip(route, route[1:]):
        add_track(board, net, layer, start, end, width_mm)
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


def remove_old_ground_escape(board: pcbnew.BOARD) -> None:
    selected = {
        item_key(item): item
        for item in board.GetTracks()
        if item_key(item) in REMOVE_GND_UUIDS
    }
    missing = REMOVE_GND_UUIDS.difference(selected)
    if missing:
        raise RuntimeError(f"Reviewed U19 GND copper is missing: {', '.join(sorted(missing))}")
    for uuid, item in selected.items():
        if item.GetNetname() != GND_NET or item.GetLayer() != pcbnew.F_Cu:
            raise RuntimeError(f"U19 GND item changed net/layer: {uuid}")
        board.RemoveNative(item)


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
    u19_cs = pad(board, "U19", "1")
    j2_cs = pad(board, "J2", "2")
    u19_gnd = pad(board, "U19", "2")
    j2_gnd = pad(board, "J2", "6")
    if u19_cs.GetNetname() != SIGNAL_NET or j2_cs.GetNetname() != SIGNAL_NET:
        raise RuntimeError("microSD CS endpoint assignment changed")
    if u19_gnd.GetNetname() != GND_NET or j2_gnd.GetNetname() != GND_NET:
        raise RuntimeError("microSD ground endpoint assignment changed")

    added_tracks = 0
    added_vias = 0
    if not connected(board, u19_cs, j2_cs):
        remove_old_ground_escape(board)
        ground = board.FindNet(GND_NET)
        signal = board.FindNet(SIGNAL_NET)
        if ground is None or signal is None:
            raise RuntimeError("Required microSD net is missing")

        added_tracks += add_route(board, ground, pcbnew.F_Cu, GND_ROUTE, 0.20)
        added_tracks += add_route(board, signal, pcbnew.F_Cu, FRONT_ROUTE, 0.15)
        add_via(board, signal, SIGNAL_VIA)
        added_vias += 1
        added_tracks += add_route(board, signal, pcbnew.B_Cu, BACK_ROUTE, 0.15)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "U19", "1"), pad(reloaded, "J2", "2")):
        raise RuntimeError("U19.1 is still disconnected from J2.2")
    if not connected(reloaded, pad(reloaded, "U19", "2"), pad(reloaded, "J2", "6")):
        raise RuntimeError("Rehomed U19.2 is not connected to GND")

    print(
        f"Saved microSD CS socket candidate: {output_path}; "
        f"tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
