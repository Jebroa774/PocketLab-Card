"""Generate or selectively remove short direct ordinary-signal candidates.

The script is deliberately paired with a full KiCad DRC run.  It records the
UUID of every added item so rejected candidates can be removed without ever
touching pre-existing copper on the same net.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pcbnew

from route_plane_fanouts import B, F, item_key, pad_layer, xy
from route_remaining_signals import (
    disconnected_pad_group_cache,
    disconnected_pad_groups,
    endpoint_candidates,
    pad_label,
    routable_nets,
)


def common_layers(start: pcbnew.PAD, end: pcbnew.PAD) -> tuple[int, ...]:
    start_layer = pad_layer(start)
    end_layer = pad_layer(end)
    start_layers = (start_layer,) if start_layer is not None else (F, B)
    end_layers = (end_layer,) if end_layer is not None else (F, B)
    return tuple(layer for layer in start_layers if layer in end_layers)


def add_direct(
    board: pcbnew.BOARD,
    net_name: str,
    start: pcbnew.PAD,
    end: pcbnew.PAD,
    layer: int,
    width_mm: float,
) -> pcbnew.PCB_TRACK:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start.GetPosition())
    track.SetEnd(end.GetPosition())
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)
    return track


def route_candidates(
    board: pcbnew.BOARD,
    requested: tuple[str, ...],
    maximum_distance: float,
    maximum_routes: int,
    width_mm: float,
) -> list[dict[str, object]]:
    candidates: list[tuple[float, str, pcbnew.PAD, pcbnew.PAD, int]] = []
    groups_by_net = disconnected_pad_group_cache(board)
    for net_name in routable_nets(board, requested, groups_by_net):
        groups = groups_by_net[net_name]
        for distance_mm, start, end in endpoint_candidates(groups):
            layers = common_layers(start, end)
            if not layers or distance_mm > maximum_distance:
                continue
            candidates.append((distance_mm, net_name, start, end, layers[0]))
            break
    candidates.sort(key=lambda entry: (entry[0], entry[1]))

    manifest: list[dict[str, object]] = []
    used_nets: set[str] = set()
    for distance_mm, net_name, start, end, layer in candidates:
        if len(manifest) >= maximum_routes:
            break
        if net_name in used_nets:
            continue
        track = add_direct(board, net_name, start, end, layer, width_mm)
        used_nets.add(net_name)
        entry = {
            "uuid": item_key(track),
            "net": net_name,
            "start": pad_label(start),
            "end": pad_label(end),
            "layer": board.GetLayerName(layer),
            "distance_mm": round(distance_mm, 6),
        }
        manifest.append(entry)
        print(
            f"CANDIDATE {net_name}: {entry['start']} -> {entry['end']}; "
            f"{entry['layer']}; {distance_mm:.2f} mm",
            flush=True,
        )
    return manifest


def remove_manifest_items(
    board: pcbnew.BOARD,
    manifest: list[dict[str, object]],
    drop_nets: frozenset[str],
) -> int:
    targets = {
        str(entry["uuid"])
        for entry in manifest
        if str(entry["net"]) in drop_nets
    }
    found = [item for item in board.GetTracks() if item_key(item) in targets]
    if len(found) != len(targets):
        present = {item_key(item) for item in found}
        raise RuntimeError(f"Manifest items absent from PCB: {sorted(targets - present)}")
    for item in found:
        board.RemoveNative(item)
    return len(found)


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--net", action="append", default=[])
    parser.add_argument("--max-distance", type=float, default=15.0)
    parser.add_argument("--max-routes", type=int, default=24)
    parser.add_argument("--track-width", type=float, default=0.15)
    parser.add_argument("--drop-net", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    manifest_path = args.manifest.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    if args.drop_net:
        if not manifest_path.is_file():
            raise RuntimeError(f"Manifest does not exist: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        drop_nets = frozenset(
            name if name.startswith("/") else f"/{name}" for name in args.drop_net
        )
        removed = remove_manifest_items(board, manifest, drop_nets)
        print(f"Removed rejected direct candidates: {removed}", flush=True)
    else:
        manifest = route_candidates(
            board,
            tuple(args.net),
            args.max_distance,
            args.max_routes,
            args.track_width,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Manifest: {manifest_path}; candidates={len(manifest)}", flush=True)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved direct-signal candidate: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
