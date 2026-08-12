"""Route the via-free LF-RFID analogue/resonance island deterministically.

The input must already contain the placement produced by ``build_pcb.py`` and
merged by ``merge_lf_rfid_placement.py``.  All sensitive HTRC110 nets stay on
B.Cu.  The fitted/DNP tuning capacitors share straight TX2/TAP buses, while the
high-voltage antenna path uses 0.60-mm copper except for the deliberately tight
0.40-mm passage between U4 and the J5 through-hole projection.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


B = pcbnew.B_Cu

SEGMENTS: tuple[
    tuple[str, float, int, tuple[float, float], tuple[float, float]], ...
] = (
    # ANT_A: fitted damping branch plus the removable coil connector.  The
    # connector branch goes around C505 rather than crossing its TX1 pad.
    ("/LF_ANT_A", 0.60, B, (35.7000, 57.2500), (36.7125, 56.2375)),
    ("/LF_ANT_A", 0.60, B, (36.7125, 56.2375), (36.7125, 53.7000)),
    ("/LF_ANT_A", 0.60, B, (35.7000, 57.2500), (34.2000, 58.7500)),
    ("/LF_ANT_A", 0.60, B, (34.2000, 58.7500), (34.2000, 60.2250)),
    ("/LF_ANT_A", 0.60, B, (34.2000, 60.2250), (36.2000, 62.2250)),
    # TX1 exits the left SO14 row directly toward the series capacitor.
    ("/LF_TX1", 0.60, B, (40.5250, 57.2200), (38.5000, 57.2200)),
    ("/LF_TX1", 0.60, B, (38.5000, 57.2200), (36.6000, 59.1500)),
    ("/LF_TX1", 0.60, B, (36.6000, 59.1500), (35.7000, 59.1500)),
    # ANT_B reaches R502 directly from the second coil terminal.
    ("/LF_ANT_B", 0.60, B, (36.2000, 64.7650), (37.0000, 64.7650)),
    ("/LF_ANT_B", 0.60, B, (37.0000, 64.7650), (38.9075, 64.2000)),
    # Parallel tuning bank: upper pads are TX2, lower pads are TAP.
    ("/LF_TX2", 0.60, B, (40.5250, 59.7600), (38.8000, 59.7600)),
    ("/LF_TX2", 0.60, B, (38.8000, 59.7600), (38.8000, 61.9000)),
    ("/LF_TX2", 0.60, B, (38.8000, 61.9000), (42.8000, 61.9000)),
    ("/LF_TX2", 0.60, B, (42.8000, 61.9000), (43.7400, 62.8000)),
    ("/LF_TX2", 0.60, B, (43.7400, 62.8000), (43.7400, 63.2500)),
    ("/LF_TX2", 0.60, B, (43.7400, 63.2500), (45.6000, 63.4250)),
    ("/LF_TX2", 0.60, B, (45.6000, 63.4250), (47.2000, 63.4250)),
    ("/LF_TAP", 0.60, B, (41.8325, 64.2000), (42.7000, 65.0675)),
    ("/LF_TAP", 0.60, B, (42.7000, 65.0675), (43.7400, 65.1500)),
    ("/LF_TAP", 0.60, B, (43.7400, 65.1500), (45.6000, 64.9750)),
    ("/LF_TAP", 0.60, B, (45.6000, 64.9750), (47.2000, 64.9750)),
    ("/LF_TAP", 0.40, B, (47.2000, 64.9750), (47.2000, 67.0000)),
    # One 0.40-mm TAP route fits between U4 pad 1 and J5 pad 1 with at least
    # the normal 0.25-mm copper clearance on both sides.
    ("/LF_TAP", 0.40, B, (47.2000, 64.9750), (48.2500, 63.9250)),
    ("/LF_TAP", 0.40, B, (48.2500, 63.9250), (48.2900, 60.5000)),
    ("/LF_TAP", 0.40, B, (48.2900, 60.5000), (54.3000, 60.5000)),
    ("/LF_TAP", 0.40, B, (54.3000, 60.5000), (54.3000, 58.3000)),
    ("/LF_TAP", 0.40, B, (54.3000, 58.3000), (53.6125, 57.5000)),
    # Local HTRC analogue conditioning.
    ("/LF_CEXT", 0.25, B, (45.4750, 58.4900), (46.5000, 58.4900)),
    ("/LF_CEXT", 0.25, B, (46.5000, 58.4900), (47.6000, 56.1000)),
    ("/LF_QGND", 0.25, B, (45.4750, 59.7600), (46.6000, 59.7600)),
    ("/LF_QGND", 0.25, B, (46.6000, 59.7600), (47.3000, 58.9000)),
    ("/LF_QGND", 0.25, B, (47.3000, 58.9000), (49.5000, 58.0050)),
    ("/LF_QGND", 0.25, B, (49.5000, 58.0050), (50.4000, 57.1050)),
    ("/LF_QGND", 0.25, B, (50.4000, 57.1050), (50.4000, 55.2500)),
    ("/LF_QGND", 0.25, B, (50.4000, 55.2500), (51.3500, 54.3000)),
    ("/LF_RX", 0.25, B, (45.4750, 61.0300), (46.8000, 61.0300)),
    ("/LF_RX", 0.25, B, (46.8000, 61.0300), (46.8000, 60.4000)),
    ("/LF_RX", 0.25, B, (46.8000, 60.4000), (48.0000, 59.4000)),
    ("/LF_RX", 0.25, B, (48.0000, 59.4000), (49.5000, 59.5550)),
    ("/LF_RX", 0.25, B, (49.5000, 59.5550), (50.5000, 58.5550)),
    ("/LF_RX", 0.25, B, (50.5000, 58.5550), (51.7875, 57.5000)),
    # The oscillator route skirts the left side of U4 and runs immediately
    # below the NFC component reserve, above the LF analogue component row.
    ("/LF_CLK_4M", 0.20, B, (40.5250, 54.6800), (38.5000, 54.6800)),
    ("/LF_CLK_4M", 0.20, B, (38.5000, 54.6800), (38.5000, 52.6000)),
    ("/LF_CLK_4M", 0.20, B, (38.5000, 52.6000), (58.8500, 52.6000)),
    ("/LF_CLK_4M", 0.20, B, (58.8500, 52.6000), (58.8500, 53.9250)),
)

ROUTED_NETS = frozenset(segment[0] for segment in SEGMENTS)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def add_routes(board: pcbnew.BOARD) -> int:
    for track in list(board.GetTracks()):
        if track.GetNetname() in ROUTED_NETS:
            board.Delete(track)

    added = 0
    for net_name, width_mm, layer, start, end in SEGMENTS:
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required LF net is missing: {net_name}")
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(width_mm))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)
        added += 1
    return added


def validate(board: pcbnew.BOARD) -> None:
    for net_name in ROUTED_NETS:
        items = [track for track in board.GetTracks() if track.GetNetname() == net_name]
        if not items:
            raise RuntimeError(f"LF route is missing {net_name}")
        if any(isinstance(track, pcbnew.PCB_VIA) for track in items):
            raise RuntimeError(f"Via found on sensitive LF net {net_name}")
        if any(track.GetLayer() != pcbnew.B_Cu for track in items):
            raise RuntimeError(f"Non-B.Cu track found on sensitive LF net {net_name}")


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == main_board:
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    added = add_routes(board)
    validate(board)
    pcbnew.SaveBoard(str(output_path), board)

    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(f"Saved LF-RFID routed PCB: {output_path}; added_segments={added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
