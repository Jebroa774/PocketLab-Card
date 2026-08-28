"""Restore reviewed copper pours onto a zone-stripped reroute candidate."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--zone-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    source = pcbnew.LoadBoard(str(args.zone_source.resolve()))
    # A full autorouter export may temporarily mark the inner power layers as
    # signal layers.  Restore the reviewed stackup semantics together with the
    # pours so the resulting KiCad candidate matches the project stackup.
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        board.SetLayerType(layer, source.GetLayerType(layer))
        board.SetLayerName(layer, source.GetLayerName(layer))
    existing = {
        (zone.GetZoneName(), zone.GetNetname(), zone.GetLayer())
        for zone in board.Zones()
        if not zone.GetIsRuleArea()
    }
    restored = 0
    for source_zone in source.Zones():
        if source_zone.GetIsRuleArea():
            continue
        key = (
            source_zone.GetZoneName(),
            source_zone.GetNetname(),
            source_zone.GetLayer(),
        )
        if key in existing:
            continue
        zone = pcbnew.ZONE(board)
        zone.SetZoneName(source_zone.GetZoneName())
        zone.SetLayer(source_zone.GetLayer())
        zone.SetOutline(source_zone.Outline())
        zone.SetLocalClearance(source_zone.GetLocalClearance())
        zone.SetMinThickness(source_zone.GetMinThickness())
        zone.SetPadConnection(source_zone.GetPadConnection())
        zone.SetThermalReliefGap(source_zone.GetThermalReliefGap())
        zone.SetThermalReliefSpokeWidth(source_zone.GetThermalReliefSpokeWidth())
        zone.SetMinIslandArea(source_zone.GetMinIslandArea())
        zone.SetAssignedPriority(source_zone.GetAssignedPriority())
        net_name = source_zone.GetNetname()
        if net_name:
            net = board.FindNet(net_name)
            if net is None:
                raise RuntimeError(f"Target board is missing zone net: {net_name}")
            zone.SetNet(net)
        board.Add(zone)
        existing.add(key)
        restored += 1

    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError("Zone fill failed")
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix))
    print(f"RESTORED_ZONES {restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
