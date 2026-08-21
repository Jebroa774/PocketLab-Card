"""Place the three remaining isolated power test pads on reviewed copper."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


TARGETS = {
    "TP107": (pcbnew.B_Cu, (84.7500, 52.0000), "/VSYS"),
}

ROUTES = (
    ("/VSYS", pcbnew.B_Cu, (84.7500, 52.0000), (85.8000, 50.9500), 0.50),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def one_pad(footprint: pcbnew.FOOTPRINT) -> pcbnew.PAD:
    pads = list(footprint.Pads())
    if len(pads) != 1:
        raise RuntimeError(
            f"Expected one pad on {footprint.GetReference()}, got {len(pads)}"
        )
    return pads[0]


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(start))
    track.SetEnd(point(end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def connected_to_other_copper(board: pcbnew.BOARD, pad: pcbnew.PAD) -> bool:
    board.BuildConnectivity()
    own_uuid = pad.m_Uuid.AsString()
    return any(
        item.m_Uuid.AsString() != own_uuid
        for item in board.GetConnectivity().GetConnectedItems(pad)
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
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    for reference, (layer, position, net_name) in TARGETS.items():
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"Missing footprint: {reference}")
        pad = one_pad(footprint)
        if pad.GetNetname() != net_name:
            raise RuntimeError(
                f"{reference} net changed: {pad.GetNetname()} != {net_name}"
            )
        if footprint.GetLayer() != layer:
            footprint.Flip(
                footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT
            )
        footprint.SetPosition(point(position))
        footprint.SetLocked(True)

    for net_name, layer, start, end, width_mm in ROUTES:
        add_track(board, net_name, layer, start, end, width_mm)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}",
            output_path.with_suffix(suffix),
        )

    reloaded = pcbnew.LoadBoard(str(output_path))
    failed = []
    for reference in TARGETS:
        footprint = reloaded.FindFootprintByReference(reference)
        if footprint is None or not connected_to_other_copper(
            reloaded, one_pad(footprint)
        ):
            failed.append(reference)
    if failed:
        raise RuntimeError(
            "Test-point connectivity failed: " + ", ".join(failed)
        )
    reloaded.BuildConnectivity()
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"Saved power-test-point candidate: {output_path}; "
        f"moved={len(TARGETS)}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
