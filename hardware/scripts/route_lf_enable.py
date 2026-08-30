"""Complete the reviewed U22 LF-enable escape without disturbing L2/GND.

U22.1 sits inside a dense front-side pocket.  The former +3V3 fanout via at
71.5000/41.7625 is redundant, but it blocks the only rule-clean escape between
the neighbouring SPI track and C313.  This pass removes that redundant fanout,
shortens the isolated R109 branch to the existing +3V3 via chain, and uses the
freed site for a 0.45/0.20-mm LF_RFID_EN via.  A 0.20-mm L3 route then joins the
already reviewed LF-enable via at 32.3875/52.775.  L2 remains plane-only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


LF_NET = "/LF_RFID_EN"
THREE_VOLT_NET = "/+3V3"

R109_BRANCH_UUID = "678d66cc-79e9-4133-a847-d4b946267baf"
REMOVE_UUIDS = frozenset(
    {
        "051bf15a-2977-4fbd-961c-0c1eff6196b4",  # redundant +3V3 via
        "85ed083e-1d31-4944-8985-67a03a61b159",  # old via branch
        "939ba718-82b3-48ab-ab3d-300cf5ace836",  # old via branch
        "d1349471-e466-454c-908f-c64f5b2a8e9f",  # obsolete branch overrun
    }
)

R109_START = (76.8125, 40.2950)
R109_NEW_END = (76.7500, 41.9500)
LF_VIA = (71.5000, 41.7625)

F_ROUTE = (
    (73.6500, 42.0500),
    (72.3000, 41.7500),
    LF_VIA,
)

L3_ROUTE = (
    LF_VIA,
    (69.7000, 41.7625),
    (59.1000, 52.3625),
    (59.1000, 52.5625),
    (59.0000, 52.6625),
    (33.0000, 52.6625),
    (32.3875, 52.7750),
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def close(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return abs(first[0] - second[0]) < 1e-6 and abs(first[1] - second[1]) < 1e-6


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
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(0.20))
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


def add_route(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    route: tuple[tuple[float, float], ...],
) -> int:
    for start, end in zip(route, route[1:]):
        add_track(board, net, layer, start, end)
    return len(route) - 1


def prepare_escape_pocket(board: pcbnew.BOARD) -> None:
    wanted = set(REMOVE_UUIDS) | {R109_BRANCH_UUID}
    selected = {
        item_key(item): item
        for item in board.GetTracks()
        if item_key(item) in wanted
    }
    missing = wanted.difference(selected)
    if missing:
        raise RuntimeError(f"Reviewed escape copper is missing: {', '.join(sorted(missing))}")

    branch = selected[R109_BRANCH_UUID]
    if not isinstance(branch, pcbnew.PCB_TRACK) or isinstance(branch, pcbnew.PCB_VIA):
        raise RuntimeError("R109 branch UUID is not a track segment")
    if branch.GetNetname() != THREE_VOLT_NET or branch.GetLayer() != pcbnew.B_Cu:
        raise RuntimeError("R109 branch net/layer changed")
    if not close(xy(branch.GetStart()), R109_START):
        raise RuntimeError(f"R109 branch start changed: {xy(branch.GetStart())}")
    branch.SetEnd(point(*R109_NEW_END))

    for uuid in REMOVE_UUIDS:
        item = selected[uuid]
        if item.GetNetname() != THREE_VOLT_NET:
            raise RuntimeError(f"Escape-pocket item changed net: {uuid}")
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
    footprint_count = len(list(board.GetFootprints()))
    u22_enable = pad(board, "U22", "1")
    u18_enable = pad(board, "U18", "9")
    u17_enable = pad(board, "U17", "3")
    if any(candidate.GetNetname() != LF_NET for candidate in (u22_enable, u18_enable, u17_enable)):
        raise RuntimeError("LF-enable endpoint net assignment changed")

    added_tracks = 0
    added_vias = 0
    if connected(board, u22_enable, u18_enable):
        print("Already connected: /LF_RFID_EN U22.1", flush=True)
    else:
        prepare_escape_pocket(board)
        lf_net = board.FindNet(LF_NET)
        if lf_net is None:
            raise RuntimeError(f"Missing PCB net: {LF_NET}")

        added_tracks += add_route(board, lf_net, pcbnew.F_Cu, F_ROUTE)

        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(*LF_VIA))
        via.SetWidth(pcbnew.FromMM(0.45))
        via.SetDrill(pcbnew.FromMM(0.20))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(lf_net)
        via.SetLocked(True)
        board.Add(via)
        added_vias += 1

        added_tracks += add_route(board, lf_net, pcbnew.In2_Cu, L3_ROUTE)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if len(list(reloaded.GetFootprints())) != footprint_count:
        raise RuntimeError("LF-enable save/reload changed the footprint count")
    if not connected(reloaded, pad(reloaded, "U22", "1"), pad(reloaded, "U18", "9")):
        raise RuntimeError("U22.1 is still disconnected from U18.9 after routing")
    if not connected(reloaded, pad(reloaded, "U22", "1"), pad(reloaded, "U17", "3")):
        raise RuntimeError("U22.1 is still disconnected from the LF-enable trunk")

    print(
        f"Saved LF-enable PCB: {output_path}; tracks={added_tracks}; vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
