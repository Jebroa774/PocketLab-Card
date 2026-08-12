# Footprint sources and status

The generated board uses stock KiCad 10 footprints where the exact package is
available. Every schematic symbol with a footprint is loaded and pad-audited by
`scripts/build_pcb.py`; the build stops if a required pin is absent or an
unexpected electrical pad is present.

Project-local footprints:

| Footprint | Basis | Release note |
|---|---|---|
| `PocketLab_Card:ESP32-S3-WROOM-1_PhysicalCourtyard` | KiCad 10 `RF_Module:ESP32-S3-WROOM-1`; only the oversized antenna-inclusive courtyard was replaced by an 18.70 x 26.10 mm physical-body courtyard, 0.25 mm beyond the stock F.Fab body outline | The stock 48 x 21 mm multilayer antenna keepout, pads, Fab, Silk and 3D model remain unchanged; U1 is assigned this variant by the schematic generator |
| `E07-900MM10S` | Ebyte's official 10 x 10 mm, 20-pad mechanical drawing and pin table | Verify the received castellated module, pin-1 orientation and pin-6 antenna escape before assembly |
| `T3-868M_Edge_Solder` | DreamLNK T3-868M 17 x 5.5 mm cylindrical spring envelope plus one electrical feed pad and a marked nonconductive free-end anchor | Hand fit only; never solder the free end, tune with the final board/enclosure, and keep the 18.8 x 6.58 mm pocket free of copper and enclosure metal |
| `TSAL6200_LayFlat_Inboard` | Vishay TSAL6200 body envelope with project-defined 90-degree formed leads | Use a forming jig; confirm polarity and keep all three optical bodies inside the rounded card outline |
| `Dupont_Grid_6x5_P2.54mm` | Project-defined row-major 30-pad matrix using 1.0 mm drills | Individual leads/short strips only; compare pad numbering with `docs/pinout.md` before wiring |
| `TPS63070_RNM0015A` | TI MPQF446A / drawing 4222000 Rev. B | Asymmetric power lands and split paste require 1:1 fabrication review |
| `BMP390_LGA-10_2x2mm` | Bosch BST-BMP390-DS002-07 | Manufacturer bottom view was mirrored to the component-side land pattern; inspect pin 1 in the assembler viewer |
| `TSOP75338WTR_HeimdallW_SideView` | Vishay drawing 6.550-5300.01-4 | Keep the optical face at the board edge and verify reel orientation |
| `Coilcraft_XFL4020` | Coilcraft XFL4020 drawing 745-3 | Used by L6; verify selected inductor suffix and height |
| `Cyntec_HBME042A-1R0MS` | TI part callout plus Cyntec HBLE042A official land drawing | Used by L7; verify the orderable suffix and received geometry |
| `NFC_Loop_35x27mm_4T_TUNE` | Original four-turn 0.50/0.50-mm PCB geometry | Prototype only; final matching must be measured on the assembled card with a VNA |
| `CSD16406Q3_VSON-8_3.3x3.3mm_P0.65mm_JLC` | KiCad 10 NexFET VSON footprint and TI CSD16406Q3 DQG package; signal lands 1-4 narrowed by 0.01 mm | Keeps the minimum different-net pad gap at JLCPCB's 0.15 mm limit; verify the exact DQG land/stencil pattern in the assembler viewer |
| `EastRising_ER-OLED0.42-1W_SolderFPC` | EastRising ER-OLED0.42-1 mechanical drawing: 12 x 11 mm glass and 16 contacts at 0.65 mm pitch; local WRL is only a dimensioned 3D preview | Manual fine-pitch operation: solder the FPC first, inspect every joint, then fold and bond the glass; verify pin 1 and contact side against the received panel before assembly |

Primary source links are embedded in each `.kicad_mod` description so they
remain visible in KiCad's footprint properties. The NFC footprint also embeds
a 36 x 29 mm all-copper-layer foreign-copper and component keepout, including
its inner opening. None of these files is a substitute for the final 1:1 PDF,
paste/mask, pin-1 and JLCPCB assembly-viewer sign-off before ordering.
