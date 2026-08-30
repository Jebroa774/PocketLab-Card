"""Route the exposed J5 I2C/SPI branches through their shunt protectors.

The long header branches use ordinary low-speed signal corridors on In2.Cu;
L2 remains an uninterrupted ground plane.  Surface-mount endpoints receive
short outer-layer escapes and standard 0.45/0.20-mm through vias.  The script
only writes a candidate board and verifies the affected endpoint trees after
save/reload.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


SDA = "/I2C_SDA_HDR"
PWR = "/+3V3"

# U23.8 already reaches the retained +3V3 plane fanout to the west.  This
# duplicate east-side via/track bundle occupies the only standard-via escape
# from U24.1 and can be removed without opening the U23 supply connection.
REMOVE_BY_NET = {
    PWR: frozenset(
        {
            "1bfd7d01-93ea-49a0-b537-420da7c88285",
            "1c0a4670-629f-4309-a52e-4d55faba92af",
            "539e313f-a814-4bd8-9a41-d97864c7c1de",
            "709dd932-cf6f-4419-bdb0-df0a4fea84b3",
            "73983cd9-4943-4fbb-92cb-8bbaa5741755",
            "86c8bc13-924a-4ae1-894b-55d7e93749f5",
            "e27c6a9a-26d7-4adf-8f28-eda13b86bd1a",
        }
    )
}

# (net, layer, start, end); all ordinary signal traces are 0.20 mm.
TRACKS = (
    (SDA, pcbnew.F_Cu, (45.3500, 64.1375), (45.3500, 65.2000)),
    (SDA, pcbnew.F_Cu, (45.3500, 65.2000), (45.1000, 65.9000)),
    (SDA, pcbnew.In2_Cu, (45.1000, 65.9000), (43.7000, 66.5000)),
    (SDA, pcbnew.In2_Cu, (43.7000, 66.5000), (43.7000, 68.2700)),
    (SDA, pcbnew.In2_Cu, (43.7000, 68.2700), (58.5400, 68.2700)),
    (SDA, pcbnew.In2_Cu, (58.5400, 68.2700), (59.8100, 69.5400)),
)

# (net, x, y); standard tented through-vias.
VIAS = (
    (SDA, 45.1000, 65.9000),
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


def connected(board: pcbnew.BOARD, first: pcbnew.BOARD_ITEM, second: pcbnew.BOARD_ITEM) -> bool:
    board.BuildConnectivity()
    wanted = item_key(second)
    return any(
        item_key(candidate) == wanted
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def checks(board: pcbnew.BOARD) -> tuple[tuple[str, pcbnew.PAD, pcbnew.PAD], ...]:
    return (
        ("I2C_SDA_HDR J5.23 -> U24.1", pad(board, "J5", "23"), pad(board, "U24", "1")),
        ("+3V3 U23.8 -> R204.2", pad(board, "U23", "8"), pad(board, "R204", "2")),
    )


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(0.20))
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, x_mm: float, y_mm: float) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(x_mm, y_mm))
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
    footprint_count = len(list(board.GetFootprints()))
    already_connected = all(connected(board, first, second) for _, first, second in checks(board))
    added_tracks = 0
    added_vias = 0
    if not already_connected:
        wanted = set().union(*REMOVE_BY_NET.values())
        selected = {item_key(item): item for item in board.GetTracks() if item_key(item) in wanted}
        missing = wanted.difference(selected)
        if missing:
            raise RuntimeError(f"Reviewed redundant copper is missing: {', '.join(sorted(missing))}")
        for net_name, uuids in REMOVE_BY_NET.items():
            changed = [uuid for uuid in uuids if selected[uuid].GetNetname() != net_name]
            if changed:
                raise RuntimeError(f"Reviewed {net_name} copper changed net: {', '.join(changed)}")
        for item in selected.values():
            board.RemoveNative(item)

        net = board.FindNet(SDA)
        if net is None:
            raise RuntimeError(f"Missing PCB net: {SDA}")
        for _net_name, layer, start, end in TRACKS:
            add_track(board, net, layer, start, end)
        for _net_name, x_mm, y_mm in VIAS:
            add_via(board, net, x_mm, y_mm)
        added_tracks = len(TRACKS)
        added_vias = len(VIAS)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if len(list(reloaded.GetFootprints())) != footprint_count:
        raise RuntimeError("Header protection save/reload changed the footprint count")
    failed = [label for label, first, second in checks(reloaded) if not connected(reloaded, first, second)]
    if failed:
        raise RuntimeError(f"Header protection connectivity failed: {', '.join(failed)}")
    print(
        f"Saved header protection candidate: {output_path}; "
        f"added_tracks={added_tracks}; added_vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
