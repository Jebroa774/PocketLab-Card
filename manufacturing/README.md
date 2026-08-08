# Manufacturing outputs

This folder will hold only generated and reviewed release artifacts:

- Gerber and drill files
- Pick-and-place / component-position file
- Assembly BOM with supplier part numbers
- Schematic and assembly PDFs
- PCB fabrication notes and stack-up
- Antenna variant notes

The first order should be five top-side SMT assembled boards, with expansion
headers, 5 mm IR LED and optional E07 radio module left unpopulated for hand
installation. The CORE-ECO variant omits BMI270 and BMP390; FULL requires
Standard PCBA. NFC matching values may need rework after V1 antenna tests, so
the first PCB must include accessible 0603 matching components and an RF test
point.

Before upload, generate a BOM containing supplier part numbers and a CPL with
unambiguous rotations. Review every polarized or pin-1 part in the JLCPCB 2D
viewer; do not accept automatic rotations without that visual check.

The 85.60 x 53.98 mm outline must remain the delivered shape. Ask JLCPCB to
place Economic-PCBA tooling holes and fiducials on 5 mm break-off mouse-bite
rails, not in the card itself. Edge-located USB/antenna components require an
explicit DFM check against rail clearance and the normal 2.5 mm body-to-edge
rule.
