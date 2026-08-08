# Footprint sources and status

The placement draft uses stock KiCad 10 footprints whenever the exact package
is available. The E07 footprint was imported with KiCad 10 from Ebyte's
official `E07-900M10S.PcbLib`, then supplemented with fabrication and courtyard
outlines. Its 22 pads, 1.27 mm pitch and 20 x 14 mm module body survived the
conversion round trip.

Source: <https://www.cdebyte.com/products/E07-900M10S/1>

Still represented only by labeled placement envelopes:

- TPS63070 RNM0015A VQFN-HR-15 and its tightly coupled inductor/passives
- BMP390 Bosch LGA-10
- TSOP75338WTR SMD MiniCast IR receiver
- the calculated/tuned PCB NFC loop

These envelopes deliberately have no fake pads. Each receives a manufacturer-
verified custom footprint during detailed schematic capture, before any routing
or manufacturing output is generated.
