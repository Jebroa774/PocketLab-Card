# PocketLab Card – Großbauteil-Layout

Dieser Ordner bewahrt den bisherigen PCB-Stand mit den größeren und teilweise
manuell zu montierenden Bauteilen. Er wurde am 17. August 2026 vor einer
möglichen späteren Ablösung des Hauptlayouts archiviert.

Enthalten sind:

- `PocketLab-Card-large-components.kicad_pcb` – unveränderte Kopie des
  bisherigen Hauptboards aus `hardware/PocketLab-Card.kicad_pcb`
- `PocketLab-Card-large-components.kicad_pro` – zugehörige KiCad-Projekteinstellungen
- `PocketLab-Card-large-components.kicad_dru` – zugehörige Designregeln
- `PocketLab-Card-large-components-drc.json` – Prüfstand mit 16 DRC-Meldungen
  und 159 noch offenen Verbindungen

Kennzeichnend für diese Variante sind unter anderem die drei liegenden
TSAL6200-THT-IR-LEDs, KMR2-Taster sowie größere 0805-, 1206- und
1210-Bauteile. Das Layout ist ein Routing-Zwischenstand und nicht
produktionsfertig.

Die Schaltplandatei wurde nicht dupliziert, weil ihr aktueller Stand bereits
von diesem archivierten PCB-Zwischenstand abweichen kann. Für eine Fortsetzung
dieser Variante sollte zuerst die Netzlisten-/Schaltplanparität geprüft werden.

Archivquelle: Commit `644adf24fc94ed19b25fa6ac94114e8d47135f6a`.
