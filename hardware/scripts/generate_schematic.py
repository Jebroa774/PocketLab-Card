"""Generate the electrically connected PocketLab Card V1 KiCad schematic.

The design is intentionally kept as one large A0 sheet.  Local net labels are
used because they remain inspectable and are reliably understood by KiCad's
own ERC/netlist exporter.  The source data below is also emitted as JSON for
the PCB synchronization script.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional


def kicad_share() -> Path:
    return Path(sys.executable).resolve().parent.parent / "share" / "kicad"


os.environ.setdefault("KICAD_SYMBOL_DIR", str(kicad_share() / "symbols"))

import kicad_sch_api as ksa  # noqa: E402


NC = None
R0805 = "Resistor_SMD:R_0805_2012Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
L0805 = "Inductor_SMD:L_0805_2012Metric"
FB0805 = "Inductor_SMD:L_0805_2012Metric"
SOT23_6 = "Package_TO_SOT_SMD:SOT-23-6"
NFC_LOOP_DESCRIPTION = (
    "Prototype PN532 PCB antenna; 4T, 35x27 mm, 0.5/0.5 mm; "
    "tune assembled board with VNA"
)


@dataclass(frozen=True)
class Part:
    block: str
    lib_id: str
    reference: str
    value: str
    footprint: str
    x: float
    y: float
    pins: Dict[str, Optional[str]]
    fields: Dict[str, str] = field(default_factory=dict)
    dnp: bool = False
    in_bom: bool = True


PARTS: list[Part] = []


def add(
    block: str,
    lib_id: str,
    reference: str,
    value: str,
    footprint: str,
    x: float,
    y: float,
    pins: Dict[str, Optional[str]],
    **fields: str,
) -> None:
    dnp = str(fields.get("DNP", "")).strip().lower() in {"1", "true", "yes"}
    # Test pads, the solder bridge and the etched PCB antenna are board
    # structures, not purchasable line items.  Their stock footprints already
    # carry the matching exclude-from-BOM attribute.
    in_bom = not (reference.startswith("TP") or reference in {"AE1", "SJ1"})
    PARTS.append(
        Part(block, lib_id, reference, value, footprint, x, y, pins, fields, dnp, in_bom)
    )


def passive(
    block: str,
    reference: str,
    value: str,
    footprint: str,
    x: float,
    y: float,
    a: str,
    b: str,
    **fields: str,
) -> None:
    symbol = "Device:C" if reference.startswith("C") else "Device:R"
    if reference.startswith("L"):
        symbol = "Device:L"
    elif reference.startswith("FB"):
        symbol = "Device:FerriteBead"
    add(block, symbol, reference, value, footprint, x, y, {"1": a, "2": b}, **fields)


def build_power() -> None:
    b = "01 USB / BATTERY / POWER"
    add(b, "Connector:USB_C_Receptacle_USB2.0_14P", "J1", "USB-C DATA/POWER",
        "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", 63.5, 76.2,
        {"A1": "GND", "A4": "VBUS_USB", "A5": "USB_CC1", "A6": "USB_CONN_P",
         "A7": "USB_CONN_N", "A9": "VBUS_USB", "A12": "GND", "B1": "GND",
         "B4": "VBUS_USB", "B5": "USB_CC2", "B6": "USB_CONN_P",
         "B7": "USB_CONN_N", "B9": "VBUS_USB", "B12": "GND", "SH": "USB_SHIELD"},
        Manufacturer="HRO", MPN="TYPE-C-31-M-12", LCSC="C165948")
    passive(b, "R101", "5.1k 1%", R0805, 101.6, 50.8, "USB_CC1", "GND")
    passive(b, "R102", "5.1k 1%", R0805, 114.3, 50.8, "USB_CC2", "GND")
    passive(b, "R103", "1M", R0805, 127.0, 50.8, "USB_SHIELD", "GND")
    passive(b, "C101", "4.7nF 1kV", C0805, 139.7, 50.8, "USB_SHIELD", "GND")
    add(b, "Device:Polyfuse", "F1", "Littelfuse 1206L075/13.2", "Fuse:Fuse_1206_3216Metric", 101.6, 76.2,
        {"1": "VBUS_USB", "2": "VBUS_FUSED"})
    add(b, "Device:D_Zener", "D101", "SMF5.0A", "Diode_SMD:D_SOD-123F", 114.3, 76.2,
        {"1": "VBUS_FUSED", "2": "GND"}, Manufacturer="Littelfuse", MPN="SMF5.0A")
    add(b, "Power_Protection:USBLC6-4SC6", "U16", "USBLC6-4SC6Y", SOT23_6, 139.7, 76.2,
        {"1": "USB_CONN_P", "2": "GND", "3": "USB_CONN_N", "4": "USB_CC1",
         "5": "VBUS_FUSED", "6": "USB_CC2"}, Manufacturer="ST", MPN="USBLC6-4SC6Y")

    add(b, "Connector_Generic:Conn_01x02", "J4", "PROTECTED 1S LiPo 3.7V",
        "Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal", 63.5, 127.0,
        {"1": "CELL_POS", "2": "CELL_NEG"}, Manufacturer="JST", MPN="S2B-PH-SM4-TB")
    add(b, "Battery_Management:BQ297xy", "U14", "BQ29700DSE", "Package_SON:WSON-6_1.5x1.5mm_P0.5mm",
        101.6, 127.0, {"1": NC, "2": "BAT_COUT", "3": "BAT_DOUT", "4": "CELL_NEG",
                       "5": "BAT_SENSE", "6": "BAT_VMINUS"}, Manufacturer="TI", MPN="BQ29700DSER")
    passive(b, "R104", "330R", R0805, 127.0, 114.3, "CELL_POS", "BAT_SENSE")
    passive(b, "C102", "100nF", C0805, 139.7, 114.3, "BAT_SENSE", "CELL_NEG")
    passive(b, "R105", "2.2k", R0805, 152.4, 114.3, "BAT_VMINUS", "GND")
    add(b, "Connector_Generic:Conn_01x05", "Q2", "CSD16406Q3 DISCHARGE",
        "PocketLab_Custom:CSD16406Q3_VSON-8_3.3x3.3mm_P0.65mm_JLC", 127.0, 139.7,
        {"1": "CELL_NEG", "2": "CELL_NEG", "3": "CELL_NEG", "4": "BAT_DOUT", "5": "BAT_FET_MID"},
        Manufacturer="TI", MPN="CSD16406Q3")
    add(b, "Connector_Generic:Conn_01x05", "Q3", "CSD16406Q3 CHARGE",
        "PocketLab_Custom:CSD16406Q3_VSON-8_3.3x3.3mm_P0.65mm_JLC", 152.4, 139.7,
        {"1": "GND", "2": "GND", "3": "GND", "4": "BAT_COUT", "5": "BAT_FET_MID"},
        Manufacturer="TI", MPN="CSD16406Q3")
    passive(b, "R106", "5.1M", R0805, 127.0, 165.1, "BAT_DOUT", "CELL_NEG")
    passive(b, "R107", "5.1M", R0805, 152.4, 165.1, "BAT_COUT", "GND")
    for index, net in enumerate(("CELL_POS", "CELL_NEG", "BAT_FET_MID", "GND"), start=101):
        add(b, "Connector:TestPoint", f"TP{index}", f"BATTERY {net}",
            "TestPoint:TestPoint_Pad_D1.0mm", 101.6 + (index - 101) * 17.78, 177.8, {"1": net})

    add(b, "Battery_Management:BQ24074RGT", "U5", "BQ24074RGTR",
        "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm_ThermalVias", 203.2, 101.6,
        {"1": "CHG_TS", "2": "CELL_POS", "3": "CELL_POS", "4": "CHG_DISABLE", "5": "BQ_EN2",
         "6": "BQ_EN1", "7": "CHARGER_PGOOD_N", "8": "GND", "9": "CHARGER_CHG_N",
         "10": "VSYS", "11": "VSYS", "12": "CHG_ILIM", "13": "VBUS_FUSED",
         "14": "CHG_TMR", "15": "CHG_ITERM", "16": "CHG_ISET", "17": "GND"},
        Manufacturer="TI", MPN="BQ24074RGTR", LCSC="C54313")
    add(b, "Jumper:SolderJumper_2_Bridged", "SJ1", "TS FIXED / CUT FOR EXT NTC",
        "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", 165.1, 127.0,
        {"1": "CHG_TS", "2": "CHG_TS_FIXED"})
    passive(b, "R108", "10k TS fixed", R0805, 177.8, 127.0, "CHG_TS_FIXED", "GND")
    add(b, "Connector_Generic:Conn_01x02", "J7", "OPTIONAL 10k NTC - CUT SJ1",
        "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", 177.8, 139.7,
        {"1": "CHG_TS", "2": "GND"})
    passive(b, "R109", "100k", R0805, 190.5, 127.0, "CHARGER_PGOOD_N", "+3V3")
    passive(b, "R110", "100k", R0805, 203.2, 127.0, "CHARGER_CHG_N", "+3V3")
    passive(b, "R111", "3.48k 1%", R0805, 215.9, 127.0, "CHG_ILIM", "GND")
    passive(b, "R112", "3.01k 1%", R0805, 228.6, 127.0, "CHG_ITERM", "GND")
    passive(b, "R113", "1.78k 1%", R0805, 241.3, 127.0, "CHG_ISET", "GND")
    passive(b, "R114", "68.1k 1%", R0805, 254.0, 127.0, "CHG_TMR", "GND")
    passive(b, "R115", "100k", R0805, 266.7, 127.0, "BQ_EN1", "GND")
    passive(b, "R126", "100k", R0805, 279.4, 127.0, "CHG_DISABLE", "GND")
    passive(b, "R128", "100k", R0805, 292.1, 127.0, "BQ_EN2", "GND")
    passive(b, "C103", "4.7uF 10V", C0805, 177.8, 152.4, "VBUS_FUSED", "GND")
    passive(b, "C104", "22uF 10V", C0805, 190.5, 152.4, "CELL_POS", "GND")
    passive(b, "C105", "4.7uF 10V", C0805, 203.2, 152.4, "VSYS", "GND")
    passive(b, "C106", "100nF", C0805, 215.9, 152.4, "VBUS_FUSED", "GND")
    passive(b, "C121", "100nF", C0805, 228.6, 152.4, "CELL_POS", "GND")
    passive(b, "C122", "100nF", C0805, 241.3, 152.4, "VSYS", "GND")

    add(b, "Connector_Generic:Conn_01x15", "U6", "TPS63070RNMR 3V3", "PocketLab_Custom:TPS63070_RNM0015A",
        63.5, 215.9, {"1": "U6_PS_SYNC", "2": "PWR_3V3_PG", "3": "U6_VAUX", "4": "GND",
                        "5": "U6_FB", "6": NC, "7": "+3V3", "8": "+3V3", "9": "U6_L2",
                        "10": "GND", "11": "U6_L1", "12": "VSYS", "13": "VSYS",
                        "14": "U6_PS_SYNC", "15": "GND"}, Manufacturer="TI", MPN="TPS63070RNMR", LCSC="C109322")
    add(b, "Device:L", "L6", "1.5uH XFL4020-152ME", "PocketLab_Custom:Coilcraft_XFL4020", 101.6, 203.2,
        {"1": "U6_L1", "2": "U6_L2"})
    passive(b, "R116", "10k", R0805, 114.3, 203.2, "VSYS", "U6_PS_SYNC")
    passive(b, "R117", "470k 1%", R0805, 127.0, 203.2, "+3V3", "U6_FB")
    passive(b, "R118", "150k 1%", R0805, 139.7, 203.2, "U6_FB", "GND")
    passive(b, "R119", "10k", R0805, 152.4, 203.2, "PWR_3V3_PG", "+3V3")
    passive(b, "C107", "100nF", C0805, 101.6, 228.6, "U6_VAUX", "GND")
    passive(b, "C108", "10uF", C0805, 114.3, 228.6, "VSYS", "GND")
    passive(b, "C109", "10uF DNP - populate only after VSYS stability test", C0805, 127.0, 228.6,
            "VSYS", "GND", DNP="true")
    for i in range(110, 113):
        passive(b, f"C{i}", "22uF", C0805, 114.3 + (i - 108) * 12.7, 228.6, "+3V3", "GND")
    passive(b, "C123", "10uF 25V X5R HF", C0603, 177.8, 228.6, "VSYS", "GND")
    passive(b, "C124", "10uF 25V X5R HF", C0603, 190.5, 228.6, "+3V3", "GND")

    add(b, "Connector_Generic:Conn_01x06", "U7", "TPS61023DRLR 5V BOOST",
        "Package_TO_SOT_SMD:SOT-563", 215.9, 203.2,
        {"1": "U7_FB", "2": "BOOST5_EN", "3": "VSYS", "4": "GND", "5": "U7_SW", "6": "+5V_RAW"},
        Manufacturer="TI", MPN="TPS61023DRLR", LCSC="C919459")
    add(b, "Device:L", "L7", "1uH HBME042A", "PocketLab_Custom:Cyntec_HBME042A-1R0MS", 241.3, 203.2,
        {"1": "VSYS", "2": "U7_SW"})
    passive(b, "R120", "732k 1%", R0805, 254.0, 203.2, "+5V_RAW", "U7_FB")
    passive(b, "R121", "100k 1%", R0805, 266.7, 203.2, "U7_FB", "GND")
    passive(b, "R122", "100k", R0805, 279.4, 203.2, "BOOST5_EN", "GND")
    passive(b, "C113", "220pF C0G", C0603, 254.0, 228.6, "+5V_RAW", "U7_FB")
    passive(b, "C114", "10uF", C0805, 266.7, 228.6, "VSYS", "GND")
    passive(b, "C115", "22uF", C0805, 279.4, 228.6, "+5V_RAW", "GND")
    passive(b, "C116", "22uF", C0805, 292.1, 228.6, "+5V_RAW", "GND")

    add(b, "Connector_Generic:Conn_01x06", "U15", "TPS2553DBVR 500mA LIMIT", SOT23_6, 215.9, 254.0,
        {"1": "+5V_RAW", "2": "GND", "3": "AUX5_EN", "4": "AUX5_FAULT_N",
         "5": "U15_ILIM", "6": "+5V_AUX"}, Manufacturer="TI", MPN="TPS2553DBVR")
    passive(b, "R123", "60.4k 1%", R0805, 241.3, 254.0, "U15_ILIM", "GND")
    passive(b, "R124", "100k", R0805, 254.0, 254.0, "AUX5_FAULT_N", "+3V3")
    passive(b, "R127", "100k", R0805, 254.0, 266.7, "AUX5_EN", "GND")
    passive(b, "C117", "10uF", C0805, 266.7, 254.0, "+5V_RAW", "GND")
    passive(b, "C118", "100nF", C0805, 279.4, 254.0, "+5V_AUX", "GND")
    passive(b, "C119", "10uF", C0805, 292.1, 254.0, "+5V_AUX", "GND")

    add(b, "Connector_Generic:Conn_01x09", "U8", "MAX17048G+T10",
        "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm", 101.6, 266.7,
        {"1": "GND", "2": NC, "3": "CELL_POS", "4": "GND", "5": "FG_ALERT_N",
         "6": "GND", "7": "I2C_SCL", "8": "I2C_SDA", "9": "GND"},
        Manufacturer="Analog Devices", MPN="MAX17048G+T10", LCSC="C2682616")
    passive(b, "R125", "10k", R0805, 127.0, 266.7, "FG_ALERT_N", "+3V3")
    passive(b, "C120", "100nF", C0805, 139.7, 266.7, "CELL_POS", "GND")

    for index, net in enumerate(("GND", "VBUS_FUSED", "CELL_NEG", "+3V3", "+5V_RAW", "+5V_AUX", "GNSS_3V3"), start=101):
        add(b, "power:PWR_FLAG", f"#FLG{index}", "PWR_FLAG", "", 165.1 + (index - 101) * 12.7, 279.4, {"1": net})

    for index, net in enumerate(("VBUS_USB", "VBUS_FUSED", "VSYS", "+3V3", "+5V_RAW", "+5V_AUX"), start=105):
        add(b, "Connector:TestPoint", f"TP{index}", f"POWER {net}",
            "TestPoint:TestPoint_Pad_D1.0mm", 177.8 + (index - 105) * 17.78, 292.1, {"1": net})


def build_mcu() -> None:
    b = "02 ESP32-S3 MCU / USB"
    add(b, "RF_Module:ESP32-S3-WROOM-1", "U1", "ESP32-S3-WROOM-1-N8R2",
        "PocketLab_Card:ESP32-S3-WROOM-1_PhysicalCourtyard", 355.6, 114.3,
        {"1": "GND", "2": "+3V3", "3": "ESP_EN", "4": "GPIO4_MCU", "5": "I2C_SDA",
         "6": "I2C_SCL", "7": "NFC_IRQ_N", "8": "SUBGHZ_GDO0", "9": "SUBGHZ_GDO2",
         "10": "SD_CS_N", "11": "GNSS_TIMEPULSE", "12": "GPIO8_MCU", "13": "USB_D_N",
         "14": "USB_D_P", "15": "JTAG_STRAP_TP", "16": "STRAP_BOOT_TP", "17": "GPIO9_MCU",
         "18": "RGB_DATA", "19": "SPI_MOSI", "20": "SPI_SCK", "21": "SPI_MISO",
         "22": "SUBGHZ_CS_N", "23": "GNSS_RX_FROM_MODULE", "24": "GPIO47_MCU",
         "25": "GPIO48_MCU", "26": "STRAP_VDD_SPI_TP", "27": "BOOT_N",
         "28": "GNSS_TX_TO_MODULE", "29": "IR_TX", "30": "IR_RX", "31": "BUZZER_PWM",
         "32": "IOEXP_INT_N", "33": "GPIO40_MCU", "34": "GPIO41_MCU", "35": "GPIO42_MCU",
         "36": "GPIO44_MCU", "37": "GPIO43_MCU", "38": "GPIO2_MCU", "39": "GPIO1_MCU",
         "40": "GND", "41": "GND"}, Manufacturer="Espressif", MPN="ESP32-S3-WROOM-1-N8R2", LCSC="C2913204")
    passive(b, "R201", "22R", R0805, 317.5, 177.8, "USB_CONN_N", "USB_D_N")
    passive(b, "R202", "22R", R0805, 330.2, 177.8, "USB_CONN_P", "USB_D_P")
    passive(b, "R203", "10k", R0805, 342.9, 177.8, "ESP_EN", "+3V3")
    passive(b, "R204", "10k", R0805, 355.6, 177.8, "BOOT_N", "+3V3")
    passive(b, "C201", "1uF", C0805, 368.3, 177.8, "ESP_EN", "GND")
    passive(b, "C202", "10uF", C0805, 381.0, 177.8, "+3V3", "GND")
    passive(b, "C203", "100nF", C0805, 393.7, 177.8, "+3V3", "GND")
    add(b, "Switch:SW_Push", "SW1", "RESET", "Button_Switch_SMD:SW_SPST_TL3305A", 342.9, 203.2,
        {"1": "ESP_EN", "2": "GND"})
    add(b, "Switch:SW_Push", "SW2", "BOOT", "Button_Switch_SMD:SW_SPST_TL3305A", 368.3, 203.2,
        {"1": "BOOT_N", "2": "GND"})
    for index, net in enumerate(("JTAG_STRAP_TP", "STRAP_BOOT_TP", "STRAP_VDD_SPI_TP"), start=201):
        add(b, "Connector:TestPoint", f"TP{index}", net, "TestPoint:TestPoint_Pad_D1.0mm", 317.5 + (index - 201) * 25.4,
            228.6, {"1": net})


def build_nfc() -> None:
    b = "03 PN532 NFC / TUNABLE LOOP"
    add(b, "RF_NFC:PN5321A3HN_C1xx", "U2", "PN5321A3HN/C106",
        "Package_DFN_QFN:HVQFN-40-1EP_6x6mm_P0.5mm_EP4.1x4.1mm", 520.7, 114.3,
        {"1": "GND", "2": "NFC_LOADMOD", "3": "GND", "4": "NFC_TX1", "5": "NFC_DVDD",
         "6": "NFC_TX2", "7": "GND", "8": "NFC_DVDD", "9": "NFC_VMID", "10": "NFC_RX",
         "11": "GND", "12": NC, "13": NC, "14": "NFC_OSCIN", "15": "NFC_OSCOUT",
         "16": "NFC_I0", "17": "GND", "18": "GND", "19": NC, "20": NC, "21": NC,
         "22": NC, "23": "+3V3", "24": NC, "25": "NFC_IRQ_N", "26": NC,
         "27": "I2C_SCL", "28": "I2C_SDA", "29": NC, "30": NC, "31": NC, "32": NC,
         "33": NC, "34": NC, "35": NC, "36": NC, "37": "NFC_SVDD", "38": "NFC_RESET_N",
         "39": "NFC_DVDD", "40": "+3V3", "41": "GND"}, Manufacturer="NXP", MPN="PN5321A3HN/C106", LCSC="C880904")
    passive(b, "R301", "10k", R0805, 482.6, 177.8, "NFC_I0", "NFC_DVDD")
    passive(b, "R302", "10k RESET default asserted", R0805, 495.3, 177.8, "NFC_RESET_N", "GND")
    passive(b, "C301", "100nF", C0805, 508.0, 177.8, "NFC_VMID", "GND")
    passive(b, "C302", "100nF AVDD", C0805, 520.7, 177.8, "NFC_DVDD", "GND")
    passive(b, "C303", "4.7uF VBAT bulk", C0805, 533.4, 177.8, "+3V3", "GND")
    passive(b, "C304", "100nF", C0805, 546.1, 177.8, "NFC_DVDD", "GND")
    passive(b, "C305", "100nF", C0805, 558.8, 177.8, "NFC_SVDD", "GND")
    passive(b, "C313", "10uF DVDD bulk", C0805, 596.9, 177.8, "NFC_DVDD", "GND")
    passive(b, "C314", "100nF TVDD", C0805, 609.6, 177.8, "NFC_DVDD", "GND")
    passive(b, "C315", "4.7uF TVDD bulk", C0805, 622.3, 177.8, "NFC_DVDD", "GND")
    passive(b, "C316", "100nF PVDD", C0805, 635.0, 177.8, "+3V3", "GND")
    passive(b, "C317", "100nF VBAT", C0805, 647.7, 177.8, "+3V3", "GND")
    # kicad-sch-api 0.5.x serializes Device:Crystal_GND24 incorrectly.  The
    # four-pad connector symbol preserves the exact electrical pin mapping;
    # the PCB still receives the real shielded-crystal footprint.
    add(b, "Connector_Generic:Conn_01x04", "Y301", "27.12MHz crystal (pins 2/4 shield)", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", 482.6, 203.2,
        {"1": "NFC_OSCIN", "2": "GND", "3": "NFC_OSCOUT", "4": "GND"})
    passive(b, "C306", "22pF C0G", C0603, 508.0, 203.2, "NFC_OSCIN", "GND")
    passive(b, "C307", "22pF C0G", C0603, 520.7, 203.2, "NFC_OSCOUT", "GND")
    passive(b, "L301", "560nH C0G/Q", L0805, 482.6, 241.3, "NFC_TX1", "NFC_TX1_F")
    passive(b, "L302", "560nH C0G/Q", L0805, 495.3, 241.3, "NFC_TX2", "NFC_TX2_F")
    passive(b, "C308", "220pF C0G", C0603, 508.0, 241.3, "NFC_TX1_F", "GND")
    passive(b, "C309", "220pF C0G", C0603, 520.7, 241.3, "NFC_TX2_F", "GND")
    passive(b, "R303", "0R MATCH", R0805, 533.4, 241.3, "NFC_TX1_F", "NFC_LOOP_A")
    passive(b, "R304", "0R MATCH", R0805, 546.1, 241.3, "NFC_TX2_F", "NFC_LOOP_B")
    passive(b, "C310", "DNP MATCH", C0603, 558.8, 241.3, "NFC_LOOP_A", "NFC_LOOP_B", DNP="true")
    passive(b, "C311", "DNP MATCH", C0603, 571.5, 241.3, "NFC_LOOP_A", "GND", DNP="true")
    passive(b, "C312", "DNP MATCH", C0603, 584.2, 241.3, "NFC_LOOP_B", "GND", DNP="true")
    passive(b, "R305", "2.7k RX TAP", R0805, 533.4, 266.7, "NFC_LOOP_A", "NFC_RX_AC")
    passive(b, "C318", "1nF C0G RX COUPLING", C0603, 546.1, 266.7, "NFC_RX_AC", "NFC_RX")
    passive(b, "R306", "1k VMID BIAS", R0805, 558.8, 266.7, "NFC_VMID", "NFC_RX")
    add(b, "Device:Antenna_Loop", "AE1", "PCB NFC LOOP - TUNE ON V1",
        "PocketLab_Custom:NFC_Loop_35x27mm_4T_TUNE", 571.5, 266.7,
        {"1": "NFC_LOOP_A", "2": "NFC_LOOP_B"}, Description=NFC_LOOP_DESCRIPTION)
    add(b, "Connector:TestPoint", "TP301", "NFC_LOADMOD TEST", "TestPoint:TestPoint_Pad_D1.0mm", 584.2, 203.2,
        {"1": "NFC_LOADMOD"})


def build_subghz() -> None:
    b = "04 E07 CC1101 SUB-GHZ"
    pinmap = {str(i): "GND" for i in (1, 2, 3, 4, 5, 11, 12, 20, 22)}
    pinmap.update({"6": NC, "7": NC, "8": NC, "9": "+3V3", "10": NC, "13": NC,
                   "14": "SUBGHZ_GDO2", "15": "SUBGHZ_GDO0", "16": "SUB_MISO",
                   "17": "SUB_MOSI", "18": "SUB_SCK", "19": "SUB_CS_N", "21": NC})
    add(b, "Connector_Generic:Conn_02x11_Odd_Even", "U3", "E07-900M10S IPEX 868MHz",
        "PocketLab_Custom:E07-900M10S", 698.5, 101.6, pinmap,
        Manufacturer="Ebyte", MPN="E07-900M10S")
    passive(b, "C401", "100nF", C0805, 660.4, 165.1, "+3V3", "GND")
    passive(b, "C402", "4.7uF", C0805, 673.1, 165.1, "+3V3", "GND")
    passive(b, "R401", "22R", R0805, 685.8, 165.1, "SPI_SCK", "SUB_SCK")
    passive(b, "R402", "22R", R0805, 698.5, 165.1, "SPI_MOSI", "SUB_MOSI")
    passive(b, "R403", "22R", R0805, 711.2, 165.1, "SPI_MISO", "SUB_MISO")
    passive(b, "R404", "22R", R0805, 723.9, 165.1, "SUBGHZ_CS_N", "SUB_CS_N")
    passive(b, "R406", "100k CS SAFE-HIGH", R0805, 736.6, 165.1, "SUB_CS_N", "+3V3")


def build_gnss_sd() -> None:
    b = "05 GNSS / ANTENNA / MICROSD"
    add(b, "RF_GPS:MAX-M10S", "U4", "MAX-M10S-00B", "RF_GPS:ublox_MAX", 863.6, 101.6,
        {"1": "GND", "2": "GNSS_UART_TX_MOD", "3": "GNSS_UART_RX_MOD",
         "4": "GNSS_TIMEPULSE", "5": NC, "6": NC, "7": "GNSS_3V3",
         "8": "GNSS_3V3", "9": "GNSS_RESET_N", "10": "GND", "11": "GNSS_ANT_FEED",
         "12": "GND", "13": "GNSS_LNA_EN", "14": "GNSS_VCC_RF", "15": NC,
         "16": NC, "17": NC, "18": NC}, Manufacturer="u-blox", MPN="MAX-M10S-00B", LCSC="C4153167")
    add(b, "Connector_Generic:Conn_01x06", "U17", "TPS22919DCKR GNSS LOAD SWITCH",
        "Package_TO_SOT_SMD:SOT-363_SC-70-6", 812.8, 165.1,
        {"1": "+3V3", "2": "GND", "3": "GNSS_POWER_EN", "4": NC,
         "5": "GNSS_QOD", "6": "GNSS_3V3"},
        Manufacturer="TI", MPN="TPS22919DCKR")
    passive(b, "R501", "100R QOD discharge", R0805, 838.2, 165.1, "GNSS_QOD", "GNSS_3V3")
    passive(b, "R502", "10k", R0805, 850.9, 165.1, "GNSS_RESET_N", "GNSS_3V3")
    passive(b, "R506", "100k SAFE-OFF", R0805, 838.2, 177.8, "GNSS_POWER_EN", "GND")
    passive(b, "R507", "1k UART BACKPOWER LIMIT", R0805, 850.9, 177.8,
            "GNSS_RX_FROM_MODULE", "GNSS_UART_TX_MOD")
    passive(b, "R508", "1k UART BACKPOWER LIMIT", R0805, 863.6, 177.8,
            "GNSS_TX_TO_MODULE", "GNSS_UART_RX_MOD")
    passive(b, "C501", "100nF", C0805, 863.6, 165.1, "GNSS_3V3", "GND")
    passive(b, "C502", "10uF", C0805, 876.3, 165.1, "GNSS_3V3", "GND")
    passive(b, "R505", "10R 0.25W DNP ACTIVE-ANT BIAS", R0805, 825.5, 203.2,
            "GNSS_VCC_RF", "GNSS_BIAS", DNP="true")
    passive(b, "L501", "27nH high-Q DNP ACTIVE-ANT BIAS", L0805, 838.2, 203.2,
            "GNSS_BIAS", "GNSS_ANT_FEED", DNP="true")
    passive(b, "C504", "10nF DNP ACTIVE-ANT BIAS", C0603, 850.9, 203.2,
            "GNSS_BIAS", "GND", DNP="true")
    add(b, "Device:D_TVS", "D501", "TPD1E0B04 0.13pF RF ESD",
        "Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm", 863.6, 203.2,
        {"1": "GND", "2": "GNSS_ANT_FEED"}, Manufacturer="TI", MPN="TPD1E0B04DPYR")
    add(b, "Connector:Conn_Coaxial", "J3", "GNSS ANT U.FL",
        "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", 889.0, 203.2,
        {"1": "GNSS_ANT_FEED", "2": "GND"})
    add(b, "Connector:TestPoint", "TP502", "LNA ENABLE", "TestPoint:TestPoint_Pad_D1.0mm", 939.8, 203.2,
        {"1": "GNSS_LNA_EN"})

    add(b, "Connector:Micro_SD_Card_Det2", "J2", "microSD",
        "Connector_Card:microSD_HC_Molex_104031-0811", 838.2, 266.7,
        {"1": "SD_DAT2", "2": "SD_CS_DEV", "3": "SD_MOSI", "4": "+3V3",
         "5": "SD_SCK", "6": "GND", "7": "SD_MISO", "8": "SD_DAT1",
         "9": "GND", "10": "SD_DETECT_N", "SH": "GND"})
    passive(b, "R510", "22R", R0805, 876.3, 254.0, "SD_CS_N", "SD_CS_DEV")
    passive(b, "R511", "22R", R0805, 889.0, 254.0, "SPI_MOSI", "SD_MOSI")
    passive(b, "R512", "22R", R0805, 901.7, 254.0, "SPI_SCK", "SD_SCK")
    passive(b, "R513", "22R", R0805, 914.4, 254.0, "SPI_MISO", "SD_MISO")
    for index, net in enumerate(("SD_DAT2", "SD_CS_DEV", "SD_MOSI", "SD_MISO", "SD_DAT1", "SD_DETECT_N"), start=514):
        passive(b, f"R{index}", "47k" if index < 519 else "10k", R0805,
                876.3 + (index - 514) * 12.7, 279.4, net, "+3V3")
    passive(b, "C510", "100nF", C0805, 876.3, 304.8, "+3V3", "GND")
    passive(b, "C511", "10uF", C0805, 889.0, 304.8, "+3V3", "GND")
    add(b, "Device:C", "C512", "47uF 6.3V LOW-ESR", "Capacitor_SMD:C_1210_3225Metric",
        901.7, 304.8, {"1": "+3V3", "2": "GND"}, Manufacturer="Murata",
        MPN="GRM32ER60J476ME20L")
    add(b, "Power_Protection:SRV05-4", "U19", "SRV05-4MR6T1G SD ESD",
        "Package_TO_SOT_SMD:SOT-23-6", 914.4, 304.8,
        {"1": "SD_CS_DEV", "2": "GND", "3": "SD_MOSI", "4": "SD_SCK",
         "5": "+3V3", "6": "SD_MISO"}, Manufacturer="onsemi", MPN="SRV05-4MR6T1G")


def build_ir_ui() -> None:
    b = "06 IR / RGB / BUTTONS / BUZZER"
    passive(b, "C607", "22uF 10V X5R IR BUFFER", "Capacitor_SMD:C_1206_3216Metric",
            63.5, 381.0, "+5V_RAW", "GND")
    passive(b, "C608", "100nF IR HF", C0805, 63.5, 406.4, "+5V_RAW", "GND")
    passive(b, "R601", "39R 1W pulse-rated", "Resistor_SMD:R_2512_6332Metric", 76.2, 393.7, "+5V_RAW", "IR_LED_A")
    add(b, "Device:LED", "D1", "TSAL6200 940nm", "LED_THT:LED_D5.0mm", 101.6, 393.7,
        {"1": "IR_LED_K", "2": "IR_LED_A"}, Manufacturer="Vishay", MPN="TSAL6200")
    add(b, "Transistor_FET:AO3400A", "Q1", "AO3400A IR DRIVER", "Package_TO_SOT_SMD:SOT-23", 127.0, 393.7,
        {"1": "IR_GATE", "2": "GND", "3": "IR_LED_K"}, Manufacturer="AOS", MPN="AO3400A", LCSC="C20917")
    passive(b, "R602", "100R", R0805, 152.4, 381.0, "IR_TX", "IR_GATE")
    passive(b, "R603", "100k", R0805, 152.4, 406.4, "IR_GATE", "GND")
    add(b, "Connector_Generic:Conn_01x04", "U13", "TSOP75338WTR 38kHz",
        "PocketLab_Custom:TSOP75338WTR_HeimdallW_SideView", 203.2, 393.7,
        {"1": "GND", "2": "IR_RX_VS", "3": "IR_RX", "4": "GND"}, Manufacturer="Vishay", MPN="TSOP75338WTR")
    passive(b, "R604", "100R", R0805, 228.6, 381.0, "+3V3", "IR_RX_VS")
    passive(b, "C601", "100nF", C0805, 228.6, 393.7, "IR_RX_VS", "GND")
    passive(b, "C602", "4.7uF", C0805, 228.6, 406.4, "IR_RX_VS", "GND")

    for index, x in enumerate((76.2, 114.3, 152.4, 190.5), start=1):
        din = "RGB_DIN1" if index == 1 else f"RGB_D{index-1}_{index}"
        dout = "RGB_DOUT4" if index == 4 else f"RGB_D{index}_{index+1}"
        add(b, "LED:WS2812B", f"LED{index}", "WS2812B-MINI-V3",
            "LED_SMD:LED_WS2812B-Mini_PLCC4_3.5x3.5mm", x, 457.2,
            {"1": "+3V3", "2": dout, "3": "GND", "4": din})
        passive(b, f"C{602 + index}", "100nF", C0805, x, 482.6, "+3V3", "GND")
    passive(b, "R605", "330R", R0805, 63.5, 457.2, "RGB_DATA", "RGB_DIN1")
    add(b, "Connector:TestPoint", "TP601", "RGB DOUT", "TestPoint:TestPoint_Pad_D1.0mm", 215.9, 457.2,
        {"1": "RGB_DOUT4"})

    add(b, "Device:Buzzer", "BZ1", "PKMCS0909E", "Buzzer_Beeper:Buzzer_Murata_PKMCS0909E", 76.2, 533.4,
        {"1": "+3V3", "2": "BUZZER_NEG"})
    add(b, "Transistor_FET:AO3400A", "Q4", "AO3400A BUZZER", "Package_TO_SOT_SMD:SOT-23", 101.6, 533.4,
        {"1": "BUZZER_GATE", "2": "GND", "3": "BUZZER_NEG"})
    passive(b, "R606", "100R", R0805, 127.0, 520.7, "BUZZER_PWM", "BUZZER_GATE")
    passive(b, "R607", "100k", R0805, 127.0, 546.1, "BUZZER_GATE", "GND")
    add(b, "Switch:SW_Push", "SW3", "USER A", "Button_Switch_SMD:SW_SPST_TL3305A", 177.8, 533.4,
        {"1": "USER_BUTTON_A_N", "2": "GND"})
    add(b, "Switch:SW_Push", "SW4", "USER B", "Button_Switch_SMD:SW_SPST_TL3305A", 203.2, 533.4,
        {"1": "USER_BUTTON_B_N", "2": "GND"})
    passive(b, "R608", "10k", R0805, 177.8, 558.8, "USER_BUTTON_A_N", "+3V3")
    passive(b, "R609", "10k", R0805, 203.2, 558.8, "USER_BUTTON_B_N", "+3V3")


def build_sensors_io() -> None:
    b = "07 SENSORS / RTC / IO EXPANSION"
    add(b, "Interface_Expansion:TCA9535DBR", "U9", "TCA9535PWR",
        "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", 355.6, 431.8,
        {"1": "IOEXP_INT_N", "2": "GND", "3": "GND", "4": "SD_DETECT_N",
         "5": "CHARGER_CHG_N", "6": "CHARGER_PGOOD_N", "7": "AUX5_FAULT_N", "8": "FG_ALERT_N",
         "9": "BMI_INT1", "10": "BMI_INT2", "11": "BMP_INT", "12": "GND",
         "13": "EX0_INT", "14": "EX1_INT", "15": "EX2_INT", "16": "EX3_INT",
         "17": "EX4_INT", "18": "EX5_INT", "19": "EX6_INT", "20": "EX7_INT",
         "21": "GND", "22": "I2C_SCL", "23": "I2C_SDA", "24": "+3V3"},
        Manufacturer="TI", MPN="TCA9535PWR", LCSC="C130204")
    passive(b, "R701", "3.3k", R0805, 317.5, 495.3, "I2C_SDA", "+3V3")
    passive(b, "R702", "3.3k", R0805, 330.2, 495.3, "I2C_SCL", "+3V3")
    passive(b, "R703", "10k", R0805, 342.9, 495.3, "IOEXP_INT_N", "+3V3")
    passive(b, "C701", "100nF", C0805, 355.6, 495.3, "+3V3", "GND")

    add(b, "Interface_Expansion:TCA9534", "U18", "TCA9534PWR INTERNAL CONTROL",
        "Package_SO:TSSOP-16_4.4x5mm_P0.65mm", 647.7, 431.8,
        {"1": "+3V3", "2": "GND", "3": "GND", "4": "BQ_EN1", "5": "CHG_DISABLE",
         "6": "AUX5_EN", "7": "NFC_RESET_N", "8": "GND", "9": "GNSS_POWER_EN",
         "10": "BOOST5_EN", "11": "USER_BUTTON_A_N", "12": "USER_BUTTON_B_N",
         "13": "IOEXP_INT_N", "14": "I2C_SCL", "15": "I2C_SDA", "16": "+3V3"},
        Manufacturer="TI", MPN="TCA9534PWR")
    passive(b, "C707", "100nF", C0805, 647.7, 482.6, "+3V3", "GND")

    add(b, "Connector_Generic:Conn_02x07_Odd_Even", "U10", "BMI270 (FULL OPTION)",
        "Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm", 431.8, 431.8,
        {"1": "GND", "2": NC, "3": NC, "4": "BMI_INT1", "5": "+3V3", "6": "GND",
         "7": "GND", "8": "+3V3", "9": "BMI_INT2", "10": NC, "11": NC,
         "12": "+3V3", "13": "I2C_SCL", "14": "I2C_SDA"}, Manufacturer="Bosch", MPN="BMI270", LCSC="C2836813")
    passive(b, "C702", "100nF", C0603, 419.1, 482.6, "+3V3", "GND")
    passive(b, "C703", "100nF", C0603, 431.8, 482.6, "+3V3", "GND")
    add(b, "Connector:TestPoint", "TP701", "BMI INT1", "TestPoint:TestPoint_Pad_D1.0mm", 444.5, 482.6,
        {"1": "BMI_INT1"})
    add(b, "Connector:TestPoint", "TP703", "BMI INT2", "TestPoint:TestPoint_Pad_D1.0mm", 457.2, 482.6,
        {"1": "BMI_INT2"})

    add(b, "Connector_Generic:Conn_02x05_Odd_Even", "U11", "BMP390 (FULL OPTION)",
        "PocketLab_Custom:BMP390_LGA-10_2x2mm", 495.3, 431.8,
        {"1": "+3V3", "2": "I2C_SCL", "3": "GND", "4": "I2C_SDA", "5": "GND",
         "6": "+3V3", "7": "BMP_INT", "8": "GND", "9": "GND", "10": "+3V3"},
        Manufacturer="Bosch", MPN="BMP390", LCSC="C5124834")
    passive(b, "C704", "100nF", C0603, 482.6, 482.6, "+3V3", "GND")
    passive(b, "C705", "100nF", C0603, 495.3, 482.6, "+3V3", "GND")
    add(b, "Connector:TestPoint", "TP702", "BMP INT", "TestPoint:TestPoint_Pad_D1.0mm", 508.0, 482.6,
        {"1": "BMP_INT"})

    add(b, "Timer_RTC:PCF8563T", "U12", "PCF8563T", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 571.5, 431.8,
        {"1": "RTC_OSCI", "2": "RTC_OSCO", "3": NC, "4": "GND", "5": "I2C_SDA",
         "6": "I2C_SCL", "7": NC, "8": "+3V3"}, Manufacturer="NXP", MPN="PCF8563T/5,518", LCSC="C7440")
    add(b, "Device:Crystal", "Y701", "32.768kHz CL=7pF", "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", 609.6, 431.8,
        {"1": "RTC_OSCI", "2": "RTC_OSCO"}, Manufacturer="Abracon", MPN="ABS07-32.768KHZ-7-T")
    passive(b, "C706", "100nF", C0805, 571.5, 482.6, "+3V3", "GND")

    direct = [1, 2, 4, 8, 9, 40, 41, 42, 43, 44, 47, 48]
    for offset, gpio in enumerate(direct):
        passive(b, f"R{710 + offset}", "100R", R0805, 317.5 + (offset % 6) * 25.4,
                546.1 + (offset // 6) * 25.4, f"GPIO{gpio}_MCU", f"GPIO{gpio}")

    for offset in range(8):
        passive(b, f"R{722 + offset}", "220R EXPANSION PROTECTION", R0805,
                317.5 + (offset % 4) * 25.4, 596.9 + (offset // 4) * 25.4,
                f"EX{offset}_INT", f"EX{offset}")

    header_bus = (
        (730, "I2C_SDA", "I2C_SDA_HDR", "100R"),
        (731, "I2C_SCL", "I2C_SCL_HDR", "100R"),
        (732, "SPI_SCK", "SPI_SCK_HDR", "100R"),
        (733, "SPI_MOSI", "SPI_MOSI_HDR", "100R"),
        (734, "SPI_MISO", "SPI_MISO_HDR", "100R"),
    )
    for offset, (number, internal_net, header_net, value) in enumerate(header_bus):
        passive(b, f"R{number}", value, R0805, 431.8 + offset * 25.4, 622.3,
                internal_net, header_net)

    header = {
        "1": "+3V3", "2": "GND", "3": "GPIO1", "4": "GPIO2", "5": "GPIO4", "6": "GPIO8",
        "7": "GPIO9", "8": "GPIO40", "9": "GPIO41", "10": "GPIO42", "11": "GPIO43",
        "12": "GPIO44", "13": "GPIO47", "14": "GPIO48", "15": "EX0", "16": "EX1",
        "17": "EX2", "18": "EX3", "19": "EX4", "20": "EX5", "21": "EX6", "22": "EX7",
        "23": "I2C_SDA_HDR", "24": "I2C_SCL_HDR", "25": "SPI_SCK_HDR", "26": "SPI_MOSI_HDR",
        "27": "SPI_MISO_HDR", "28": "GND", "29": "+5V_AUX", "30": "GND",
    }
    add(b, "Connector_Generic:Conn_02x15_Odd_Even", "J5", "2x15 2.54mm DUPONT EXPANSION",
        "Connector_PinHeader_2.54mm:PinHeader_2x15_P2.54mm_Vertical", 736.6, 457.2, header)


def apply_serialized_dnp_flags(output: Path, dnp_references: set[str]) -> None:
    """Work around kicad-sch-api 0.5.x always serializing ``(dnp no)``.

    The API exposes ``in_bom`` but not the symbol DNP flag.  Limit the repair
    to top-level placed-symbol blocks and verify that every requested reference
    was changed exactly once.  This keeps schematic and PCB assembly state in
    lockstep without editing generated symbols by hand.
    """
    lines = output.read_text(encoding="utf-8").splitlines(keepends=True)
    rewritten: list[str] = []
    patched: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not (line.startswith("\t(symbol") and line.strip() == "(symbol"):
            rewritten.append(line)
            index += 1
            continue

        end = index + 1
        while end < len(lines) and not (
            lines[end].startswith("\t)") and lines[end].strip() == ")"
        ):
            end += 1
        if end >= len(lines):
            raise RuntimeError("Unterminated top-level symbol in generated schematic")
        block = lines[index : end + 1]
        match = re.search(
            r'^\s*\(property "Reference" "([^"]+)"', "".join(block), re.MULTILINE
        )
        if match is None:
            raise RuntimeError("Generated top-level symbol has no Reference property")
        reference = match.group(1)
        if reference in dnp_references:
            serialized = "".join(block)
            serialized, replacements = re.subn(
                r"\(dnp no\)", "(dnp yes)", serialized, count=1
            )
            if replacements != 1:
                raise RuntimeError(f"Could not set generated DNP flag for {reference}")
            block = serialized.splitlines(keepends=True)
            patched.add(reference)
        rewritten.extend(block)
        index = end + 1

    if patched != dnp_references:
        raise RuntimeError(
            "Generated DNP symbol set mismatch; missing="
            + repr(sorted(dnp_references - patched))
            + ", extra="
            + repr(sorted(patched - dnp_references))
        )
    output.write_text("".join(rewritten), encoding="utf-8")


def unconnected_net_name(reference: str, pin_number: str, pin_name: str) -> str:
    """Mirror KiCad's stable PCB net name for a schematic no-connect pin."""
    if not pin_name:
        raise RuntimeError(f"No-connect pin {reference}.{pin_number} has no pin name")
    escaped_name = pin_name.replace("/", "{slash}")
    return f"unconnected-({reference}-{escaped_name}-Pad{pin_number})"


def emit_schematic(output: Path, design_json: Path, allow_isolated: bool = False) -> None:
    schematic = ksa.create_schematic("PocketLab Card V1")
    schematic.set_paper_size("A0")
    schematic.set_title_block(
        title="PocketLab Card V1 - Complete Electrical Capture",
        rev="V1-DESIGN",
        company="PocketLab",
        comments={1: "Prototype design - tune RF/NFC on hardware", 2: "Do not order until ERC/DRC and DFM release pass"},
    )

    titles = {
        "01 USB / BATTERY / POWER": (50.8, 38.1),
        "02 ESP32-S3 MCU / USB": (317.5, 38.1),
        "03 PN532 NFC / TUNABLE LOOP": (482.6, 38.1),
        "04 E07 CC1101 SUB-GHZ": (660.4, 38.1),
        "05 GNSS / ANTENNA / MICROSD": (812.8, 38.1),
        "06 IR / RGB / BUTTONS / BUZZER": (50.8, 355.6),
        "07 SENSORS / RTC / IO EXPANSION": (317.5, 355.6),
    }
    for title, pos in titles.items():
        schematic.add_text(title, pos, size=2.0, bold=True)

    created = {}
    for part in PARTS:
        kwargs = dict(part.fields)
        component = schematic.components.add(
            part.lib_id,
            part.reference,
            part.value,
            (part.x, part.y),
            footprint=part.footprint or None,
            **kwargs,
        )
        component.in_bom = part.in_bom
        created[part.reference] = component

    net_usage: dict[str, int] = {}
    no_connect_nets: dict[str, dict[str, str]] = {}
    for part in PARTS:
        component = created[part.reference]
        actual_pins = {pin.number for pin in component.pins}
        specified_pins = set(part.pins)
        if actual_pins != specified_pins:
            missing = sorted(actual_pins - specified_pins)
            extra = sorted(specified_pins - actual_pins)
            raise RuntimeError(f"{part.reference} pin coverage mismatch; missing={missing}, extra={extra}")

        for pin_number, net in part.pins.items():
            point = schematic.get_component_pin_position(part.reference, pin_number)
            if point is None:
                raise RuntimeError(f"Cannot locate {part.reference}.{pin_number}")
            pin = next(pin for pin in component.pins if pin.number == pin_number)
            if net is None:
                schematic.no_connects.add((point.x, point.y))
                no_connect_nets.setdefault(part.reference, {})[pin_number] = (
                    unconnected_net_name(part.reference, pin_number, pin.name)
                )
                continue

            rotation = round(pin.rotation) % 360
            # A 1.27 mm stub keeps labels snapped to the KiCad grid without
            # making two neighbouring vertical passives (12.7 mm centres)
            # meet exactly halfway and accidentally short their nets.
            stub = 1.27
            if rotation == 0:
                endpoint = (point.x - stub, point.y)
            elif rotation == 180:
                endpoint = (point.x + stub, point.y)
            elif rotation == 270:
                endpoint = (point.x, point.y - stub)
            elif rotation == 90:
                endpoint = (point.x, point.y + stub)
            else:
                raise RuntimeError(f"Unsupported pin rotation {pin.rotation} on {part.reference}.{pin_number}")
            schematic.add_wire_to_pin(endpoint, part.reference, pin_number)
            schematic.add_label(net, endpoint, size=0.8)
            net_usage[net] = net_usage.get(net, 0) + 1

    isolated = sorted(net for net, count in net_usage.items() if count < 2)
    if isolated and not allow_isolated:
        raise RuntimeError("Nets used only once: " + ", ".join(isolated))

    output.parent.mkdir(parents=True, exist_ok=True)
    schematic.save(output)
    apply_serialized_dnp_flags(output, {part.reference for part in PARTS if part.dnp})
    serialized_parts = []
    for part in PARTS:
        serialized = asdict(part)
        serialized["no_connect_nets"] = no_connect_nets.get(part.reference, {})
        serialized_parts.append(serialized)
    design_json.write_text(
        json.dumps(
            {"format": 1, "parts": serialized_parts, "net_usage": net_usage}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(PARTS)} symbols and {len(net_usage)} named nets in {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--design-json", type=Path, default=None)
    parser.add_argument("--only", choices=("power", "mcu", "nfc", "subghz", "gnss_sd", "ir_ui", "sensors_io"))
    args = parser.parse_args()

    builders = {
        "power": build_power,
        "mcu": build_mcu,
        "nfc": build_nfc,
        "subghz": build_subghz,
        "gnss_sd": build_gnss_sd,
        "ir_ui": build_ir_ui,
        "sensors_io": build_sensors_io,
    }
    if args.only:
        builders[args.only]()
    else:
        for builder in builders.values():
            builder()

    design_json = args.design_json or args.output.with_name("design-netlist.json")
    emit_schematic(args.output.resolve(), design_json.resolve(), allow_isolated=bool(args.only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
