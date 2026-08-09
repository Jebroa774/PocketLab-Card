# Footprint sources and status

The generated board uses stock KiCad 10 footprints where the exact package is
available. Every schematic symbol with a footprint is loaded and pad-audited by
`scripts/build_pcb.py`; the build stops if a required pin is absent or an
unexpected electrical pad is present.

Project-local footprints:

| Footprint | Basis | Release note |
|---|---|---|
| `E07-900M10S` | Ebyte's official `E07-900M10S.PcbLib`, imported with KiCad 10 and supplemented with Fab/Courtyard data | Verify the exact 22-pad IPEX module variant against received parts |
| `TPS63070_RNM0015A` | TI MPQF446A / drawing 4222000 Rev. B | Asymmetric power lands and split paste require 1:1 fabrication review |
| `BMP390_LGA-10_2x2mm` | Bosch BST-BMP390-DS002-07 | Manufacturer bottom view was mirrored to the component-side land pattern; inspect pin 1 in the assembler viewer |
| `TSOP75338WTR_HeimdallW_SideView` | Vishay drawing 6.550-5300.01-4 | Keep the optical face at the board edge and verify reel orientation |
| `Coilcraft_XFL4020` | Coilcraft XFL4020 drawing 745-3 | Used by L6; verify selected inductor suffix and height |
| `Cyntec_HBME042A-1R0MS` | TI part callout plus Cyntec HBLE042A official land drawing | Used by L7; verify the orderable suffix and received geometry |
| `NFC_Loop_35x27mm_4T_TUNE` | Original four-turn 0.50/0.50-mm PCB geometry | Prototype only; final matching must be measured on the assembled card with a VNA |

Primary source links are embedded in each `.kicad_mod` description so they
remain visible in KiCad's footprint properties. The NFC footprint also embeds
a 36 x 29 mm all-copper-layer foreign-copper and component keepout, including
its inner opening. None of these files is a substitute for the final 1:1 PDF,
paste/mask, pin-1 and JLCPCB assembly-viewer sign-off before ordering.
