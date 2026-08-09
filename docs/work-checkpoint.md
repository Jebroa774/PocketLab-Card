# Work checkpoint

Saved 2026-08-09 before stopping work.

## Verified at this checkpoint

- The generated main schematic contains 214 symbols and 156 named nets.
- KiCad 10.0.5 ERC completes with 0 errors and 0 warnings.
- Five manufacturer-derived custom footprints are present in
  `hardware/PocketLab_Custom.pretty`.
- The ESP32-S3 firmware builds successfully with the web portal, microSD file
  management, GNSS trip logging, U9/TCA9535 and U18/TCA9534 support.
- Sub-GHz, IR and exposed-GPIO transmit endpoints remain disabled by default.

## Resume here

1. Complete the independent schematic pin/footprint audit. The TPS22919 U17
   six-pin correction is already applied.
2. Generate the fully netlisted two-sided PCB placement from
   `hardware/design-netlist.json`.
3. Route critical power, USB, GNSS/Sub-GHz RF and NFC paths, then route the
   remaining signals and add the ground/power pours.
4. Run PCB DRC and create Gerber, drill, BOM and pick-and-place outputs.
5. Update the project status documentation, commit the final board and open it
   in KiCad for visual review.

The current PCB file is still the earlier 21-footprint placement draft and is
not yet an orderable board. Do not send it to fabrication.
