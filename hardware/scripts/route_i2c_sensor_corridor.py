"""Route the reviewed U8/U11 I2C sensor corridor without HDI vias.

The original B.Cu fanout forced SDA, SCL, FG_ALERT_N and SPI_MOSI through the
same narrow channel.  This deterministic pass removes only the reviewed
obsolete copper, connects U8 SCL to the ESP32 branch through standard
0.45/0.20-mm through vias on L3, connects U8 SDA directly to U11, and restores
FG_ALERT_N, SPI_MOSI and the two displaced U11 ground pads.  L2 remains a
ground-only plane.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


GND_NET = "/GND"
SDA_NET = "/I2C_SDA"
SCL_NET = "/I2C_SCL"
FG_NET = "/FG_ALERT_N"
SPI_NET = "/SPI_MOSI"

REMOVE_BY_NET = {
    GND_NET: frozenset(
        {
            "080654b7-d5a1-46db-8a7e-f4ee8790ec20",
            "2e278f13-8f91-4a45-9d57-91a82d2ca6e5",
            "37c70ac5-2845-4bf0-8b8e-48f200d03e7a",
            "3dc730f3-eb47-4b0a-8cd7-f4f78f532197",
            "d4b34b77-1d87-43a0-9573-36b33005ed66",
            "e631f14b-bfe5-4d9c-9b65-26d1e17b57ce",
        }
    ),
    FG_NET: frozenset(
        {
            "08c4db63-b727-48e2-a519-91c5d5fb9d59",
            "ab59e168-1855-4201-89cf-d708badb04d9",
            "bdcd6fb5-69b1-4853-843d-97b765ffc86e",
            "be0c6219-1bc1-41d6-9ad8-8e4a764adb8b",
            "ff6f5250-8232-4880-b268-828060c465da",
        }
    ),
    SPI_NET: frozenset(
        {
            "131ac254-18f3-4c16-bf7a-05fb1153ac9f",
            "1a2263a2-7d0a-483c-8623-17096e5b6c90",
            "474f78c3-8ff7-4736-8d4b-0bce1b566ff2",
            "4fe6904f-bf15-4a68-af19-714cf7b25d32",
            "5285f77e-301c-4227-9a50-e8713eabcb82",
            "5740b09e-8f88-4b9c-a0ab-03bc008fff5d",
            "6e08b5c4-45e3-455b-a539-dd1dde0ebe37",
            "7837f510-4a93-46c5-8de5-19addfc8435a",
            "7aea224e-1ca1-43a7-8807-3e4c588cbae0",
            "9e55b3ae-f95c-4e0d-80b8-b0b6869f1227",
            "d8e51563-2a35-45f1-97be-f490270fb1e3",
            "dbc0479c-4f24-4a47-a107-5ae4d25d8084",
            "e1965ff9-829a-4794-847f-e190f24546ff",
            "f591ac9c-2606-42d8-8691-edb8a68ff4e7",
            "f6577d3e-1f4a-48c1-8f98-0ad0bb4e8800",
            "fd5ddc77-cc5f-4d70-88a3-d995ac8e9582",
        }
    ),
}

# (net, layer, start, end).  All reviewed traces are 0.20 mm.
TRACKS = (
    (GND_NET, pcbnew.B_Cu, (78.7750, 33.3350), (78.7750, 34.5850)),
    (GND_NET, pcbnew.B_Cu, (78.7750, 34.5850), (78.7625, 35.2000)),
    (GND_NET, pcbnew.B_Cu, (78.7625, 36.2000), (79.6000, 36.2000)),
    (GND_NET, pcbnew.B_Cu, (79.6000, 36.2000), (79.6000, 39.3000)),
    (SDA_NET, pcbnew.B_Cu, (81.0125, 35.7500), (78.7625, 35.7000)),
    (SCL_NET, pcbnew.F_Cu, (83.8500, 33.8400), (83.5500, 34.1400)),
    (SCL_NET, pcbnew.In2_Cu, (83.5500, 34.1400), (82.2500, 35.8400)),
    (SCL_NET, pcbnew.In2_Cu, (82.2500, 35.8400), (80.1500, 37.3400)),
    (SCL_NET, pcbnew.B_Cu, (80.1500, 37.3400), (80.2500, 36.3400)),
    (SCL_NET, pcbnew.B_Cu, (80.2500, 36.3400), (80.4500, 36.2400)),
    (SCL_NET, pcbnew.B_Cu, (80.4500, 36.2400), (81.0125, 36.2500)),
    (FG_NET, pcbnew.B_Cu, (81.0125, 37.2500), (80.9125, 37.4500)),
    (FG_NET, pcbnew.In2_Cu, (80.9125, 37.4500), (80.2125, 37.9500)),
    (FG_NET, pcbnew.In2_Cu, (80.2125, 37.9500), (79.9125, 37.8500)),
    (FG_NET, pcbnew.In2_Cu, (79.9125, 37.8500), (79.6125, 37.5500)),
    (FG_NET, pcbnew.In2_Cu, (79.6125, 37.5500), (79.6125, 36.9500)),
    (FG_NET, pcbnew.In2_Cu, (79.6125, 36.9500), (81.7125, 34.5500)),
    (FG_NET, pcbnew.B_Cu, (81.7125, 34.5500), (80.9950, 33.9375)),
    (SPI_NET, pcbnew.F_Cu, (76.7625, 33.3500), (77.8125, 33.2000)),
    (SPI_NET, pcbnew.F_Cu, (77.8125, 33.2000), (77.9625, 32.7500)),
    (SPI_NET, pcbnew.F_Cu, (77.9625, 32.7500), (78.1125, 32.6000)),
    (SPI_NET, pcbnew.F_Cu, (78.1125, 32.6000), (79.4625, 31.8500)),
    (SPI_NET, pcbnew.B_Cu, (79.4625, 31.8500), (79.9125, 31.2500)),
    (SPI_NET, pcbnew.B_Cu, (79.9125, 31.2500), (82.0125, 31.2500)),
    (SPI_NET, pcbnew.B_Cu, (82.0125, 31.2500), (85.4625, 35.0000)),
    (SPI_NET, pcbnew.F_Cu, (85.4625, 35.0000), (89.3625, 38.6000)),
    (SPI_NET, pcbnew.B_Cu, (89.3625, 38.6000), (89.2125, 43.2500)),
    (SPI_NET, pcbnew.B_Cu, (89.2125, 43.2500), (89.0625, 43.4000)),
    (SPI_NET, pcbnew.B_Cu, (89.0625, 43.4000), (86.5125, 43.4000)),
    (SPI_NET, pcbnew.B_Cu, (86.5125, 43.4000), (86.0625, 44.0000)),
    (SPI_NET, pcbnew.B_Cu, (86.0625, 44.0000), (85.6125, 45.5000)),
    (SPI_NET, pcbnew.B_Cu, (85.6125, 45.5000), (85.6125, 47.1500)),
    (SPI_NET, pcbnew.B_Cu, (85.6125, 47.1500), (84.2000, 48.1875)),
)

# (net, x, y); every reviewed via is 0.45/0.20 mm and through-hole.
VIAS = (
    (SCL_NET, 83.5500, 34.1400),
    (SCL_NET, 80.1500, 37.3400),
    (FG_NET, 80.9125, 37.4500),
    (FG_NET, 81.7125, 34.5500),
    (SPI_NET, 79.4625, 31.8500),
    (SPI_NET, 85.4625, 35.0000),
    (SPI_NET, 89.3625, 38.6000),
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


def connectivity_checks(board: pcbnew.BOARD) -> tuple[tuple[str, pcbnew.PAD, pcbnew.PAD], ...]:
    return (
        ("I2C_SCL U1.6 -> U8.7", pad(board, "U1", "6"), pad(board, "U8", "7")),
        ("I2C_SDA U8.8 -> U11.4", pad(board, "U8", "8"), pad(board, "U11", "4")),
        ("FG_ALERT_N U8.5 -> R125.1", pad(board, "U8", "5"), pad(board, "R125", "1")),
        ("SPI_MOSI U21.12 -> R129.2", pad(board, "U21", "12"), pad(board, "R129", "2")),
        ("GND U11.3 -> C704.2", pad(board, "U11", "3"), pad(board, "C704", "2")),
        ("GND U11.5 -> U11.8", pad(board, "U11", "5"), pad(board, "U11", "8")),
    )


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
    already_connected = all(
        connected(board, first, second)
        for _, first, second in connectivity_checks(board)
    )
    added_tracks = 0
    added_vias = 0
    if not already_connected:
        wanted = set().union(*REMOVE_BY_NET.values())
        selected = {
            item_key(item): item
            for item in board.GetTracks()
            if item_key(item) in wanted
        }
        missing = wanted.difference(selected)
        if missing:
            raise RuntimeError(f"Reviewed corridor copper is missing: {', '.join(sorted(missing))}")
        for net_name, uuids in REMOVE_BY_NET.items():
            changed = [uuid for uuid in uuids if selected[uuid].GetNetname() != net_name]
            if changed:
                raise RuntimeError(f"Reviewed {net_name} copper changed net: {', '.join(changed)}")
        for item in selected.values():
            board.RemoveNative(item)

        nets = {
            name: board.FindNet(name)
            for name in (GND_NET, SDA_NET, SCL_NET, FG_NET, SPI_NET)
        }
        missing_nets = [name for name, net in nets.items() if net is None]
        if missing_nets:
            raise RuntimeError(f"Missing PCB nets: {', '.join(missing_nets)}")
        for net_name, layer, start, end in TRACKS:
            add_track(board, nets[net_name], layer, start, end)
        for net_name, x_mm, y_mm in VIAS:
            add_via(board, nets[net_name], x_mm, y_mm)
        added_tracks = len(TRACKS)
        added_vias = len(VIAS)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    if len(list(reloaded.GetFootprints())) != footprint_count:
        raise RuntimeError("Corridor save/reload changed the footprint count")
    failed = [
        label
        for label, first, second in connectivity_checks(reloaded)
        if not connected(reloaded, first, second)
    ]
    if failed:
        raise RuntimeError(f"Corridor connectivity failed: {', '.join(failed)}")
    print(
        f"Saved I2C sensor corridor: {output_path}; "
        f"added_tracks={added_tracks}; added_vias={added_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
