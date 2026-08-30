"""Remove the OLED block and add a compact, firmware-configurable AUX button.

This board-only migration is intentionally performed on a candidate copy.  It
removes J8, the OLED charge-pump/decoupling capacitors C610-C616 and all copper
on OLED-exclusive nets.  A C&K KXT311LHS switch is then placed in the released
top-side area and connected between ESP32-S3 GPIO21 and GND.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


OLED_REFERENCES = {"J8", *(f"C{number}" for number in range(610, 617))}
OLED_ONLY_NETS = {
    "/OLED_C1N",
    "/OLED_C1P",
    "/OLED_C2N",
    "/OLED_C2P",
    "/OLED_VCC",
    "/OLED_VCOMH",
}
# Shared-net stubs that terminated only at the removed OLED connector/capacitors.
# UUIDs keep this cleanup deliberately narrower than a generic dangling-track pass.
OLED_SHARED_STUB_UUIDS = {
    "1a75f7a7-ae69-432b-9768-c2e95d61a08b",
    "7126c4c0-0172-4e1c-aea2-0aecde26d1b4",
    "c2ccff27-fbd0-4d17-9994-0abd2a0ccc51",
    "d2e64d41-e9b7-44ff-9d36-117aa8595803",
    "d7c5614f-8257-447b-9635-095224376233",
    "c3913d69-d33e-4353-a2fe-03e7eabeaed5",
    "e269e5a1-c568-4db6-908b-ca977027193b",
    "718dd461-babc-4f03-b6e4-f32381888867",
    "11b67ae9-8291-4a5f-9114-5554c9f1b9c4",
    "dc9cccd6-cde5-4ce1-904c-fc5703edf5b4",
    "3da5a222-191c-4bcc-95d5-ad78d08d330f",
    "cba2256a-2b1b-48d9-9445-bdc2d5ea3bd0",
    "aab207fc-53a6-4ab3-bfcd-322693f0698b",
    "7fec891b-754c-4c0e-9c24-d049489d0000",
    "f6879ffd-47e5-47fa-9431-c99285de509f",
    "ce0f8ced-dc11-4577-bce8-ed01c3f12953",
    "ed1b1617-cfd9-463f-ad32-22f72d5b7ce8",
    "c303005d-ccfb-4ba5-b5b0-e649f6851aa6",
    "170d4c26-1f5b-4f19-a845-0f5493fec5e5",
    "f1318a3d-38cd-4232-80f7-57437da8d238",
}
AUX_NET = "/USER_BUTTON_AUX_N"
AUX_POSITION_MM = (92.0, 58.5)


def get_or_add_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def load_switch(library: Path) -> pcbnew.FOOTPRINT:
    footprint = pcbnew.FootprintLoad(str(library), "SW_SPST_CK_KXT3")
    if footprint is None:
        raise RuntimeError(f"Could not load KXT3 footprint from {library}")
    return footprint


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--switch-library", type=Path, required=True)
    parser.add_argument("--aux-x", type=float, default=AUX_POSITION_MM[0])
    parser.add_argument("--aux-y", type=float, default=AUX_POSITION_MM[1])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    output = args.output.resolve()
    if output == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))

    missing = sorted(
        reference
        for reference in OLED_REFERENCES
        if board.FindFootprintByReference(reference) is None
    )
    if missing:
        raise RuntimeError(f"Missing OLED references: {', '.join(missing)}")
    if board.FindFootprintByReference("SW8") is not None:
        raise RuntimeError("SW8 already exists")

    removed_copper = 0
    for item in list(board.GetTracks()):
        if (
            item.GetNetname() in OLED_ONLY_NETS
            or item.m_Uuid.AsString() in OLED_SHARED_STUB_UUIDS
        ):
            board.Delete(item)
            removed_copper += 1

    removed_footprints = 0
    for reference in sorted(OLED_REFERENCES):
        board.Delete(board.FindFootprintByReference(reference))
        removed_footprints += 1

    aux_net = get_or_add_net(board, AUX_NET)
    ground = board.FindNet("/GND")
    if ground is None:
        raise RuntimeError("GND net is missing")

    mcu = board.FindFootprintByReference("U1")
    if mcu is None:
        raise RuntimeError("ESP32 footprint U1 is missing")
    gpio21 = next((pad for pad in mcu.Pads() if pad.GetNumber() == "23"), None)
    if gpio21 is None:
        raise RuntimeError("U1 pad 23 / GPIO21 is missing")
    if gpio21.GetNetname() != "unconnected-(U1-IO21-Pad23)":
        raise RuntimeError(f"U1 pad 23 is not free: {gpio21.GetNetname()}")
    gpio21.SetNet(aux_net)

    button = load_switch(args.switch_library.resolve())
    button.SetReference("SW8")
    button.SetValue("AUX CONFIG")
    button.SetPosition(pcbnew.VECTOR2I_MM(args.aux_x, args.aux_y))
    button.SetOrientationDegrees(0.0)
    button.SetFields(
        {
            **dict(button.GetFieldsText()),
            "Manufacturer": "C&K",
            "MPN": "KXT311LHS",
            "Assembly": "PCBA_FACTORY",
            "Function": "Firmware-configurable AUX button; enable GPIO21 pull-up",
        }
    )
    for name in button.GetFieldsText():
        if name != "Reference":
            button.GetField(name).SetVisible(False)
    board.Add(button)
    for pad in button.Pads():
        if pad.GetNumber() == "1":
            pad.SetNet(aux_net)
        elif pad.GetNumber() == "2":
            pad.SetNet(ground)
        else:
            raise RuntimeError(f"Unexpected KXT3 pad number: {pad.GetNumber()}")

    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    opens = int(connectivity.GetUnconnectedCount(False))

    output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix)
        )
    print(
        f"SAVED removed_footprints={removed_footprints} "
        f"removed_oled_copper={removed_copper} added=SW8 "
        f"gpio=U1.23/{AUX_NET} opens={opens}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
