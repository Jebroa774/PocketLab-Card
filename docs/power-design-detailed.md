# Detaillierter Entwurf: USB-C, Akku und Stromversorgung

Stand: 2026-08-09. Dieses Dokument erklärt Auslegung und Prüfkriterien für den
Power-Block. Für Referenzbezeichner, Netznamen und tatsächlich bestückte
Optionen ist der aktuell erzeugte KiCad-Schaltplan maßgeblich. Es ist noch
**kein Freigabenachweis für ein Serienprodukt**. LiPo-Sicherheit, thermische
Grenzen, USB-Konformität und alle Stromgrenzen müssen am ersten Prototyp
verifiziert werden.

## 1. Festgelegte Architektur

```text
USB-C VBUS
  -> F1 1206L075/13.2
  -> VBUS_FUSED (TVS + 4.7 uF)
  -> BQ24074 IN

2-pin 1S LiPo
  CELL_POS -------------------------> BQ24074 BAT
  CELL_NEG -> BQ29700 + 2x MOSFET --> GND/PACK_NEG

BQ24074 OUT = VSYS (normal ca. 2.9 ... 4.5 V; nahe Akku-Cutoff ggf. tiefer)
  -> TPS63070 -> +3V3
  -> TPS61023 -> +5V_RAW
                    -> IR-Stufe
                    -> TPS2553 -> +5V_AUX

MAX17048 misst CELL_POS gegen System-GND.
```

Die Netzbezeichnungen sind absichtlich eindeutig:

| Netz | Bedeutung |
|---|---|
| `VBUS_USB` | USB-VBUS direkt am Stecker, vor F1 |
| `VBUS_FUSED` | Geschützter USB-Eingang nach F1 |
| `CELL_POS` | Akku-Plus und BQ24074-BAT |
| `CELL_NEG` | Akku-Minus vor den Schutz-MOSFETs; kein System-GND |
| `BAT_FET_MID` | Gemeinsame Drains der Schutz-MOSFETs |
| `GND` | `PACK_NEG`, Systemmasse nach den Schutz-MOSFETs |
| `VSYS` | BQ24074-OUT, Eingang der beiden DC/DC-Wandler |
| `+3V3` | Dauerhafte digitale 3,3-V-Schiene |
| `+5V_RAW` | Schaltbare 5-V-Schiene direkt vom TPS61023 |
| `+5V_AUX` | Separat strombegrenzte 5-V-Schiene am Header |

Die beiden Wandler-Nennwerte dürfen nicht gleichzeitig als Dauerlast
ausgenutzt werden. Schon `3.3 V * 1.5 A + 5 V * 1.0 A = 9.95 W` Ausgangsleistung
erfordern bei je 90 % Wirkungsgrad rund 11.1 W beziehungsweise 3.35 A aus
einem auf 3.3 V abgesunkenen Akku. Das überschreitet das 2-A-Dauerziel und
das 3-A-Pulsziel. Firmware muss IR, Header, NFC, RGB und Funklasten weiterhin
gegeneinander verriegeln. Bei USB500 ohne Akku stehen insgesamt höchstens
etwa 2.5 W vor Verlusten zur Verfügung; hohe Lasten benötigen den Akku als
Puffer.

## 2. USB-C-Sink und USB 2.0

### 2.1 Stecker J1

Bauteil: HRO `TYPE-C-31-M-12`, KiCad-Footprint
`Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12`.

| Kontakt(e) | Netz / Beschaltung |
|---|---|
| A4, A9, B4, B9 | gemeinsam `VBUS_USB` |
| A1, A12, B1, B12 | `GND` |
| A6, B6 | gemeinsam `USB_CONN_P` |
| A7, B7 | gemeinsam `USB_CONN_N` |
| A5 / CC1 | `USB_CC1`; eigener 5.1-kOhm-Widerstand nach GND |
| B5 / CC2 | `USB_CC2`; eigener 5.1-kOhm-Widerstand nach GND |
| A8 / SBU1, B8 / SBU2 | unbeschaltet |
| Shield-Pads | gemeinsam `USB_SHIELD`; R103 1 MOhm und C101 4.7 nF parallel nach GND |

CC1 und CC2 dürfen **nicht** miteinander verbunden werden. Je ein
`5.1 kOhm, 1 %, 0805` nach GND kennzeichnet das Board als reinen 5-V-Sink.
Es gibt kein USB-PD und ohne CC-Controller auch keine Auswertung einer
1.5-A-/3-A-Ankündigung. Die Schaltung bleibt deshalb bei höchstens USB-500.

Der Steckerschirm ist in diesem Prototyp nicht direkt mit System-GND
kurzgeschlossen. Seine Pads bilden eine kurze, zusammenhängende
`USB_SHIELD`-Kupferinsel; R103/C101 koppeln diese Insel DC-/HF-definiert an
GND. Ob für das reale Gehäuse und die EMV-Prüfung stattdessen eine direkte
Verbindung erforderlich ist, muss gemessen und dann als eigene Revision
festgelegt werden.

### 2.2 VBUS-Schutz

| Ref | Wert / Teil | Footprint | Verbindung |
|---|---|---|---|
| F1 | Littelfuse `1206L075/13.2`, 0.75 A hold, 1.5 A trip | `Fuse:Fuse_1206_3216Metric` | `VBUS_USB` -> `VBUS_FUSED` |
| D101 | Littelfuse `SMF5.0A`, unidirektional | `Diode_SMD:D_SOD-123F` | Kathode `VBUS_FUSED`, Anode GND |
| C103 | 4.7 uF, 16 V, X7R, 0805 | 0805 | `VBUS_FUSED` nach GND; zugleich U5-IN-Bypass |
| C106 | 100 nF, 16 V, X7R, 0805 | 0805 | `VBUS_FUSED` nach GND; zugleich U5-IN-Bypass |

Der 1206L075 hat bei 20 Grad C 0.75 A Haltestrom, 1.5 A Auslösestrom und
bis zu 0.35 Ohm nach Auslösung/Rückstellung laut Herstellerdaten. Bei hoher
Umgebungstemperatur ist der Haltestrom reduziert; F1 daher nicht direkt neben
dem Lade-IC platzieren. Die gesamte direkt an VBUS sichtbare Kapazität bleibt
mit 4.8 uF nominal unter 10 uF. Diese Kondensatoren dürfen an U5 nicht ein
zweites Mal bestückt werden. Die große Systemkapazität liegt hinter dem
strombegrenzenden BQ24074-Power-Path.

### 2.3 ESD und Datenleitungen

U16: ST `USBLC6-4SC6Y`, SOT-23-6L / JEDEC MO-178AB,
KiCad `Package_TO_SOT_SMD:SOT-23-6`.

| Pin | Funktion | Netz |
|---:|---|---|
| 1 | I/O1 | `USB_CONN_P` |
| 2 | GND | GND |
| 3 | I/O2 | `USB_CONN_N` |
| 4 | I/O3 | `USB_CC1` |
| 5 | VBUS | `VBUS_FUSED` |
| 6 | I/O4 | `USB_CC2` |

Das ESD-Array ist eine Abzweigklemme, kein serielles Durchgangsbauteil. Es
muss direkt hinter dem Stecker mit extrem kurzen Leitungen nach GND und
`VBUS_FUSED` sitzen. Danach folgen je `22 Ohm, 1 %, 0805` seriell in D+ und D-
zu `USB_D_P` beziehungsweise `USB_D_N` am ESP32-S3. D+ und D- werden als
90-Ohm-Differenzpaar mit durchgehender Referenzfläche, gleicher Via-Anzahl und
ohne bestückte Shunt-Kondensatoren geführt.

## 3. BQ24074 Ladegerät und Power-Path

U5: Texas Instruments `BQ24074RGTR`, RGT0016B, VQFN-16 mit Exposed Pad,
3.0 x 3.0 mm, 0.5-mm-Pitch. Verifizierter KiCad-10-Footprint:
`Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm_ThermalVias`.
Das Exposed Pad ist in KiCad Pad 17 und muss an GND liegen.

### 3.1 Pin-zu-Netz-Tabelle

| Pin | Name | Netz / Bauteil |
|---:|---|---|
| 1 | TS | `CHG_TS`; 10.0 kOhm nach GND oder externer 10-k-NTC |
| 2, 3 | BAT | `CELL_POS`; 22 uF + 100 nF nach GND |
| 4 | CE | `CHG_DISABLE`; 100 kOhm Pulldown nach GND; High sperrt Laden |
| 5 | EN2 | `BQ_EN2`; 100 kOhm Pulldown nach GND |
| 6 | EN1 | `BQ_EN1`; 100 kOhm Pulldown nach GND, MCU darf auf High schalten |
| 7 | PGOOD | `CHARGER_PGOOD_N`; 100 kOhm Pull-up nach +3V3 |
| 8 | VSS | GND |
| 9 | CHG | `CHARGER_CHG_N`; 100 kOhm Pull-up nach +3V3 |
| 10, 11 | OUT | `VSYS`; 4.7 uF + 100 nF unmittelbar nach GND |
| 12 | ILIM | 3.48 kOhm, 1 %, nach GND |
| 13 | IN | `VBUS_FUSED`; gemeinsamer C103 4.7 uF + C106 100 nF nach GND |
| 14 | TMR | 68.1 kOhm, 1 %, nach GND |
| 15 | ITERM | 3.01 kOhm, 1 %, nach GND |
| 16 | ISET | 1.78 kOhm, 1 %, nach GND |
| EP / 17 | Thermal pad | GND mit Thermal-Vias |

`PGOOD` und `CHG` sind Open-Drain-Ausgänge. Die 100-kOhm-Pull-ups sparen
Ruhestrom; falls lange Leitungen oder hohe Störlast Probleme machen, dürfen
sie ohne Schaltungsänderung auf 47 kOhm reduziert werden.

Die BQ24074-Empfehlung für die gesamte an OUT sichtbare Keramikkapazität ist
4.7 bis 47 uF. Daher werden direkt an U5 nur 4.7 uF bestückt. Am
TPS63070-Eingang werden standardmäßig nur `C108` und `C123` mit je
10 uF bestückt; `C109` bleibt DNP. Zusammen mit 10 uF am
TPS61023-Eingang entstehen damit etwa 34.7 uF nominal auf `VSYS`. Das gibt
Reserve für positive Bauteiltoleranzen und weitere unvermeidbare
Abblockkondensatoren. `C109` darf erst nach einem Stabilitäts- und
Lastsprungtest bestückt werden; dann liegen 44.7 uF nominal an `VSYS` und die
47-uF-Grenze muss einschließlich Toleranzen erneut bewertet werden.

### 3.2 Einstellwerte und Rechnungen

Ladestrom, typischer TI-Faktor `K_ISET = 890 A*Ohm`:

```text
I_CHG = K_ISET / R_ISET
      = 890 / 1780
      = 0.500 A typisch
```

Der Datenblattfaktor streut von 797 bis 975 A*Ohm. Der USB-Eingangslimiter
begrenzt den realen Ladestrom zusätzlich; 500 mA ist trotzdem nur für Zellen
zulässig, deren Hersteller mindestens diesen Ladestrom erlaubt.

Terminierungsstrom im USB500- oder ISET-Modus:

```text
I_TERM = K_ITERM * R_ITERM / R_ISET
       = 0.030 A * 3010 / 1780
       = 50.7 mA typisch
```

Safety Timer:

```text
t_MAXCHG = 10 * R_TMR * K_TMR
         = 10 * 68.1 kOhm * 48 s/kOhm
         = 32,688 s = 9.08 h typisch
```

Der Timer kann wegen `K_TMR = 36 ... 60 s/kOhm` etwa 6.81 bis 11.35 h
betragen. Die Vorladedauer ist ein Zehntel davon, typisch rund 54.5 min.
Diese längere Einstellung ist bewusst gewählt: Ein 2000-mAh-Pack benötigt
bei 500 mA bereits mindestens vier Stunden Konstantstrom plus CV-Taper; ein
6-h-Timer könnte am unteren Toleranzrand zu früh auslösen.

Der programmierbare ILIM-Ersatzmodus wird konservativ dimensioniert:

```text
R_ILIM = 3.48 kOhm, 1 %
I_LIM_typ = 1525 / 3480 = 438 mA
I_LIM_max = 1720 / (3480 * 0.99) = 499 mA
```

Damit überschreitet auch der optionale Widerstandsmodus rechnerisch 500 mA
nicht. Im normalen USB-Betrieb bestimmt jedoch EN1/EN2 den Eingangsstrom.

### 3.3 Verbindliche EN-Logik

| EN2 | EN1 | Zustand |
|---:|---:|---|
| 0 | 0 | USB100; Default nach Reset |
| 0 | 1 | USB500; erst nach erfolgreicher USB-Enumeration |
| 1 | 0 | Widerstandsmodus, hier max. ca. 499 mA |
| 1 | 1 | Standby |

Produktionsdefault ist `EN2=0`, `EN1=0`. Die aktuelle sichere Firmware lässt
EN1 dauerhaft Low und bleibt damit im USB100-Modus; eine spätere Umschaltung
auf USB500 ist nur nach einer verlässlichen Erkennung der zulässigen
Quellenstromstärke erlaubt. Im 100-mA-Startzustand müssen PN532, 5-V-Boost,
GNSS-Antennenversorgung, RGB-LEDs und externe Lasten sicher ausgeschaltet
bleiben. Falls der ESP32 unter 100 mA nicht zuverlässig startet, ist für den
Prototyp ein Akku erforderlich.

### 3.4 Akku-Temperatur

Der gewählte 2-polige JST-Stecker hat keinen Temperaturkontakt. Daher:

- R108 (`10 kOhm TS fixed`, 0805) und den gebrückten Lötjumper SJ1
  standardmäßig bestücken.
- J7 stellt zwei unbestückte THT-Pads im 2.54-mm-Raster für `CHG_TS` und GND
  bereit.
- Bei Verwendung eines echten 10-kOhm-NTC SJ1 auftrennen. Dadurch wird R108
  von `CHG_TS` getrennt; R108 muss nicht ausgelötet werden.

Ein Festwiderstand hält TS elektrisch im gültigen Bereich, misst aber **keine
Zellentemperatur**. Für ein endgültiges Produkt ist ein Akku mit drittem
NTC-Kontakt die bevorzugte Lösung. Nur Standard-LiPo/Li-Ion mit 4.20-V-
Ladeschlussspannung verwenden, keine 4.35-V-LiHV-Zelle.

### 3.5 Verlustleistung

Ungünstiger linearer Ladefall bei 5 V Eingang, etwa 3 V Akku und 0.5 A:

```text
P_U5 ~= (5.0 - 3.0) * 0.5 = 1.0 W
Delta_T ~= 1.0 W * 44.5 K/W = 44.5 K
```

Das ist nur eine JEDEC-Abschätzung. Der BQ24074 beginnt typischerweise bei
125 Grad C Sperrschichttemperatur thermisch zurückzuregeln. EP, Ground-Pour
und Vias sind deshalb funktional nötig. Im Prototyp Ladestrom und Temperatur
bei leerem Akku und gleichzeitigem Systembetrieb messen.

## 4. 1S-LiPo-Schutz

Dieser Schutz ergänzt einen geschützten Akku, ersetzt aber keine geprüfte
Schutzschaltung im Pack. Er schützt nicht gegen einen verpolten Akkustecker.
Die Kabelpolarität muss vor dem ersten Einstecken geprüft und auf dem
Silkscreen groß markiert werden.

### 4.1 Stecker

J4: JST `S2B-PH-SM4-TB`, PH-Serie, 2.0-mm-Raster, Side-Entry. Pin 1 wird
im Projekt als `CELL_POS`, Pin 2 als `CELL_NEG` festgelegt. Das ist eine
Boarddefinition; fertig konfektionierte JST-Akkukabel haben keine universell
garantierte Polarität.

### 4.2 Schutz-IC U14

U14: TI `BQ29700DSER`, DSE WSON-6, 1.5 x 1.5 x 0.75 mm, 0.5-mm-Pitch.
KiCad: `Package_SON:WSON-6_1.5x1.5mm_P0.5mm`. JLCPCB-Bestückung zwingend.

| Pin | Name | Netz / Beschaltung |
|---:|---|---|
| 1 | NC | wirklich unverbunden |
| 2 | COUT | Gate Q3; zusätzlich R107 5.1 MOhm Gate-Source |
| 3 | DOUT | Gate Q2; zusätzlich R106 5.1 MOhm Gate-Source |
| 4 | VSS | `CELL_NEG` |
| 5 | BAT | über 330 Ohm von `CELL_POS`; 100 nF von Pin 5 nach `CELL_NEG` |
| 6 | V- | über 2.2 kOhm von GND / `PACK_NEG` |

Fest programmierte Schwellen des BQ29700:

| Schutz | Schwelle | Verzögerung |
|---|---:|---:|
| Überspannung | 4.275 V | 1.25 s |
| Unterspannung | 2.800 V | 144 ms |
| Lade-Überstrom | -100 mV | 8 ms |
| Entlade-Überstrom | +100 mV | 20 ms |
| Kurzschluss | +500 mV | 250 us |

### 4.3 Schutz-MOSFETs

Q2 und Q3: je TI `CSD16406Q3`, DQG / VSON-CLIP,
3.3 x 3.3 mm, 0.65-mm-Pitch. KiCad:
`Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET`.

Physische Anschlüsse laut TI:

| Physischer Pin | Funktion |
|---:|---|
| 1, 2, 3 | Source |
| 4 | Gate |
| 5, 6, 7, 8 | Drain |

Der KiCad-Footprint fasst die physische Drainfläche 5 bis 8 absichtlich als
einen großen Pad mit Nummer 5 zusammen. Symbol und Footprint müssen deshalb
gezielt aufeinander geprüft werden; ein generisches SO-8-MOSFET-Footprint ist
falsch.

Back-to-back, Common-Drain:

| FET | Source | Drain | Gate | Gate-Source-Widerstand |
|---|---|---|---|---|
| Q2 (discharge) | `CELL_NEG` | `BAT_FET_MID` | U14 DOUT | R106 5.1 MOhm nach `CELL_NEG` |
| Q3 (charge) | GND / `PACK_NEG` | `BAT_FET_MID` | U14 COUT | R107 5.1 MOhm nach GND |

Das maximale RDS(on) eines FETs beträgt laut TI 7.4 mOhm bei VGS=4.5 V.
Nur als grobe Raumtemperatur-Abschätzung:

```text
R_pair,max ~= 2 * 7.4 mOhm = 14.8 mOhm
P_pair at 2 A ~= 2^2 * 14.8 mOhm = 59 mW
I_OCD,approx ~= 100 mV / 14.8 mOhm = 6.8 A
```

Bei niedrigem Zellpegel und hoher Temperatur steigt RDS(on) deutlich. Der
Schutz ist damit ein Fehler-/Kurzschlussschutz und **keine präzise 2-A-
Strombegrenzung**. 2 A dauerhaft und 3 A kurz müssen mit realem Pack,
Leiterbahnen, Steckverbinder und Temperatur geprüft werden. Der JST-PH-
Stecker ist mit 2 A der offensichtliche Dauerstrom-Flaschenhals. Insbesondere
kann ein längerer Fehlerstrom von etwa 3 bis 5 A unterhalb der BQ29700-
Auslöseschwelle liegen und den Stecker trotzdem überlasten. Falls nicht
bereits der gewählte Akku-Pack nachweislich in diesem Bereich abschaltet,
muss vor Serienfreigabe eine zusätzliche Sicherung oder passend ausgelegte
Hardware-Strombegrenzung in den Akkupfad aufgenommen werden.

Testpunkte TP101 (`CELL_POS`), TP102 (`CELL_NEG`), TP103 (`BAT_FET_MID`) und
TP104 (`GND`) sind
zwingend. `CELL_NEG` darf nicht auf normalen Erweiterungssteckern erscheinen,
weil das die Schutz-FETs umgehen würde. Nach Schutzabschaltung kann zum
Aufwecken das Anlegen des Ladegeräts erforderlich sein.

## 5. MAX17048 Fuel Gauge

U8: Analog Devices / Maxim `MAX17048G+T10`, TDFN-8-EP, 2.0 x 2.0 mm,
0.5-mm-Pitch. KiCad:
`Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm`; EP ist Pad 9.

| Pin | Name | Netz / Beschaltung |
|---:|---|---|
| 1 | CTG | GND |
| 2 | CELL | NC; beim MAX17048 intern nicht verbunden |
| 3 | VDD | `CELL_POS`; 100 nF direkt nach GND |
| 4 | GND | GND |
| 5 | ALRT | `FG_ALERT_N`; 10 kOhm Pull-up nach +3V3 |
| 6 | QSTRT | GND, weil Hardware-Quickstart unbenutzt |
| 7 | SCL | `I2C_SCL` |
| 8 | SDA | `I2C_SDA` |
| EP / 9 | EP | GND |

Die zentralen I2C-Pull-ups R701/R702 sind einmalig `3.3 kOhm` nach +3V3. Keine zweiten
Pull-ups auf diesem Blatt bestücken. Adresse: `0x36` (7 Bit), Bus bis 400 kHz.

Die Masse des Gauge liegt auf der Systemseite der Schutz-FETs. Dadurch
überbrückt U8 die Schutzschaltung nicht; bei geöffneten FETs verliert der
Gauge seinen Rückleiter. Typische Stromaufnahme: 23 uA aktiv, 3 uA Hibernate.
Für gute SOC-Genauigkeit muss die Firmware RCOMP mit einer gemessenen
Temperatur korrigieren; ohne Akku-NTC ist die Boardtemperatur nur ein Ersatz.

## 6. +3V3 mit TPS63070

U6: TI `TPS63070RNMR`, RNM0015A, VQFN-HR-15, nominal 3.0 x 2.5 mm,
maximal 1.0 mm hoch. Das Gehäuse besitzt ein asymmetrisches Power-Landpattern.
Es darf **kein generisches QFN** verwendet werden. Projekt-Footprint:
`PocketLab_Custom:TPS63070_RNM0015A`.

### 6.1 Pin-zu-Netz-Tabelle

| Pin | Name | Netz / Beschaltung |
|---:|---|---|
| 1 | PS/SYNC | gemeinsam mit EN hinter 10 kOhm nach `VSYS`; Power-Save/PFM aktiv |
| 2 | PG | `PWR_3V3_PG`; 10 kOhm Pull-up nach +3V3 |
| 3 | VAUX | nur 100 nF nach GND; keine externe Last |
| 4 | GND | ruhige Signalmasse |
| 5 | FB | Mittelpunkt 470 kOhm / 150 kOhm |
| 6 | FB2 | offen; laut TI alternativ GND zulässig |
| 7, 8 | VOUT | `+3V3` |
| 9 | L2 | L6 Anschluss 2 |
| 10 | PGND | Leistungsmassenfläche |
| 11 | L1 | L6 Anschluss 1 |
| 12, 13 | VIN | `VSYS` |
| 14 | EN | gemeinsam mit PS/SYNC auf `U6_PS_SYNC`, hinter R116 10 kOhm nach `VSYS` |
| 15 | VSEL | GND |

Feedback:

```text
V_OUT = 0.8 * (1 + 470k / 150k)
      = 3.3067 V
```

Das ist zugleich die von TI angegebene Standardkombination für 3.3 V.

### 6.2 Leistungsteile

| Ref | Hersteller / Teil | Wert / Eckdaten | Package |
|---|---|---|---|
| L6 | Coilcraft `XFL4020-152MEC` | 1.5 uH, Isat 4.6 A bei 30 % Abfall, DCR typ. 14.4 mOhm | 4.0 x 4.0 x 2.1 mm |
| C108 | Murata `GRM21BC71E106ME11L` | 10 uF, 25 V, X7S | 0805 |
| C109 | Murata `GRM21BC71E106ME11L` | 10 uF, 25 V, X7S; **DNP ab Werk** | 0805 |
| C123 | Taiyo Yuden `TMK107BBJ106MA-T` | 10 uF, 25 V, X5R; direkt an VIN/PGND | 0603 |
| C110/C111/C112 | Murata `GRM21BC81C226ME44L` | je 22 uF, 16 V, X6S | 0805 |
| C124 | Taiyo Yuden `TMK107BBJ106MA-T` | 10 uF, 25 V, X5R; direkt an VOUT/PGND | 0603 |
| C107 | beliebig qualifiziert | 100 nF, X7R | 0805 |
| R117 | 470 kOhm, 1 % | +3V3 nach FB | 0805 |
| R118 | 150 kOhm, 1 % | FB nach GND | 0805 |

Die Kondensator-MPNs sind aus der TI-Typapplikation. Die beiden 0603-Bypässe
gehören direkt an die IC-Pins und reduzieren die Schaltspitzen. Alternativen sind nur
nach Prüfung der **effektiven** Kapazität bei DC-Bias zulässig. Für den
einstellbaren TPS63070 fordert TI `COUT_eff [uF] >= 10 * L_eff [uH]`; bei
1.5 uH sind das mindestens 15 uF effektiv. Die 3 x 22 uF plus 10 uF nominal
geben Reserve für Bias, Toleranz und schnelle ESP32-Lastsprünge.

Konservative Boost-Abschätzung bei `VIN=3.0 V`, `VOUT=3.3 V`, `IOUT=2 A`,
`eta=90 %`, `f=2.4 MHz`, `L=1.5 uH`:

```text
I_IN,avg = 3.3 * 2 / (3.0 * 0.90) = 2.44 A
D ~= 1 - (3.0 * 0.90 / 3.3) = 0.182
Delta_I ~= VIN * D / (L * f) = 0.152 A_pp
I_peak ~= 2.44 + 0.152/2 = 2.52 A
```

Der TPS63070 spezifiziert ein **durchschnittliches** positives
Eingangsstromlimit von mindestens 3.05 A. Der korrekte Vergleich ist daher
`I_IN,avg = 2.44 A < 3.05 A`; `I_peak = 2.52 A` dient hier nur zur Prüfung
von Induktor und Schaltstromform. Das ist kein thermischer Nachweis. 1.5 A
ist der Dauerzielwert, 2.0 A ein kurzer Peak.

Beim Kaltstart gilt eine zusätzliche Grenze: Solange VOUT noch unter 3.0 V
liegt, garantiert TI den Start erst ab `VIN = 3.0 V`. Nach erfolgreichem
Start darf der Wandler bis 2.0 V weiterarbeiten. Ein nur 2.8 bis 3.0 V starker
Akku kann die Karte deshalb nach Einstecken eventuell nicht starten; USB
hebt `VSYS` zum Wiederanlauf an. Dieses Verhalten muss im Prototyp gezielt
getestet werden und ist als dokumentierte Unterspannungs-Wake-Bedingung zu
behandeln.

### 6.3 RNM0015A-Footprint

Verbindliche Quelle ist TI Package Drawing `MPQF446A`, Drawing 4222000 Rev. B.
Die TI-Landpattern-Seite nennt unter anderem:

- acht NSMD-Randpads 1 bis 6, 14 und 15 mit je 0.25 x 0.60 mm;
- die SMD-Powerpads 7 bis 13 sind zusammengesetzte Kupferformen, unter
  anderem mit vier 0.25-x-0.60-mm-Randfingern sowie 0.25-, 0.525-, 0.75- und
  1.35-mm-Abmessungen gemäß Zeichnung;
- 0.5-mm-Pitch; die Referenzmaße 2.8, 1.7, 1.15 und 0.6 mm müssen in ihrer
  gezeichneten Achse übernommen und dürfen nicht als Bounding-Box gelesen werden;
- Pads 1 bis 6, 14 und 15 non-solder-mask-defined;
- Pads 7 bis 13 solder-mask-defined;
- 0.125-mm-Schablone und 85 % Paste-Coverage für die exponierten Pads 9 bis 11.

Der Custom-Footprint muss vollständig gegen Seite 2 und 3 dieser Zeichnung
geprüft werden. Automatische Erzeugung als gleichförmiges 15-Pad-QFN ist
verboten. Vor Bestellung sind 1:1-PDF, Courtyard, Paste, Mask und Pin-1-
Kennzeichnung manuell zu kontrollieren.

Layout: L6 direkt zwischen L1 und L2, Eingangskondensatoren unmittelbar an
VIN/PGND, Ausgangskondensatoren unmittelbar an VOUT/PGND. FB-Teiler an Pin 5,
weit weg von L1/L2 und Induktor; GND-Seite des Teilers an ruhige GND-Zone.
TI fordert außerdem einen Serienwiderstand, wenn EN oder PS/SYNC fest an VIN
gebunden werden. R116 ist deshalb der gemeinsame 10-kOhm-Widerstand für beide
Pins; eine direkte beziehungsweise 0-Ohm-Verbindung von EN nach VSYS ist nicht
zulässig.

## 7. Schaltbare +5V mit TPS61023

U7: TI `TPS61023DRLR`, DRL / SOT-563-6. KiCad:
`Package_TO_SOT_SMD:SOT-563`. JLCPCB-Bestückung zwingend.

| Pin | Name | Netz / Beschaltung |
|---:|---|---|
| 1 | FB | Mittelpunkt 732 kOhm / 100 kOhm |
| 2 | EN | `BOOST5_EN`; 100 kOhm Pulldown, Steuerung über U18/P5 |
| 3 | VIN | `VSYS` |
| 4 | GND | GND |
| 5 | SW | L7 Anschluss 2 |
| 6 | VOUT | `+5V_RAW` |

| Ref | Teil / Wert | Package |
|---|---|---|
| L7 | Cyntec `HBME042A-1R0MS-99`, 1.0 uH, DCR 11.5 mOhm, Isat 7 A | 4.1 x 4.1 x 2.1 mm |
| C114 | 10 uF, >=10 V, X5R/X7R | 0805 |
| C115/C116 | je 22 uF, >=10 V, X5R/X7R | 0805 |
| R120 | 732 kOhm, 1 % | 0805 |
| R121 | 100 kOhm, 1 % | 0805 |
| C113 | 220 pF, C0G, parallel zu R120 | 0603 oder 0805 |

```text
V_OUT,typ = 0.595 * (1 + 732k / 100k) = 4.950 V
f_zero = 1 / (2*pi*732k*220pF) = 989 Hz
```

TI empfiehlt den Feed-forward-Kondensator bei mehr als 40 uF nominaler
Ausgangskapazität. Die 44 uF nominal müssen unter 5-V-DC-Bias noch genügend
effektive Kapazität liefern.

Worst-case-Abschätzung bei `VIN=3.0 V`, `VOUT=5.0 V`, `IOUT=1.5 A`,
`eta=90 %`, `f=1 MHz`, `L=1 uH`:

```text
I_IN,avg = 5.0 * 1.5 / (3.0 * 0.90) = 2.78 A
D ~= 1 - (3.0 * 0.90 / 5.0) = 0.46
Delta_I ~= 3.0 * 0.46 / (1uH * 1MHz) = 1.38 A_pp
I_valley ~= 2.78 - 1.38/2 = 2.09 A
I_peak ~= 2.78 + 1.38/2 = 3.47 A
```

Der TPS61023 begrenzt den **Valley-Strom**; `I_valley = 2.09 A` liegt unter
dem garantierten Mindestlimit von 2.7 A. `I_peak` ist dagegen gegen die
Induktorsättigung zu prüfen. Der 7-A-Induktor hat ausreichend Reserve. Der
reale Dauerzielwert der gesamten 5-V-Schiene ist 1.0 A, 1.5 A nur kurz. Die
Schiene ist nach Reset aus. `+5V_RAW` versorgt IR und den Eingang des
Header-Load-Switch; Firmware muss beide Lasten gemeinsam budgetieren.

Zur Regelschleife gehören nicht nur die beiden 22-uF-Kondensatoren direkt an
U7: Auch 10 uF + 100 nF am Eingang von U15 liegen permanent an `+5V_RAW`.
Damit sind bereits rund 54.1 uF nominal angeschlossen, zuzüglich lokaler
IR-Abblockung. Diese Gesamtkapazität bleibt weit innerhalb des von TI
erlaubten Bereichs von 4 bis 1000 uF effektiv, muss aber beim Enable-Start,
Lastsprungtest und bei der Feed-forward-Kompensation gemeinsam betrachtet
werden.

Optionaler Diagnose-ADC: 100 kOhm von `+5V_RAW` auf `ADC_5V_MON`, 33 kOhm von
dort nach GND und 10 nF nach GND. Bei 5 V entstehen ca. 1.24 V.

Die IR-Stufe erhält zusätzlich direkt am lokalen Pulsstromkreis C607 mit
22 uF/10 V X5R im handfreundlichen 1206-Gehäuse und C608 mit 100 nF im
0805-Gehäuse. Beide liegen von `+5V_RAW` nach GND und gehören räumlich zu
R601/D1/Q1, nicht zum entfernten U7-Ausgangskondensatorbank.

## 8. 500-mA-Load-Switch für den Header

U15: TI `TPS2553DBVR`, ausdrücklich **ohne `-1`**. DBV / SOT-23-6,
KiCad `Package_TO_SOT_SMD:SOT-23-6`. TPS2553 ist active-high und bleibt bei
Überlast zunächst im Konstantstrombetrieb; bei zu hoher Verlustleistung
kann er thermisch aus- und wieder einschalten. Nach Entfernen der Überlast
kehrt er selbstständig zum Normalbetrieb zurück. Die `-1`-Variante würde
dagegen verriegeln.

| Pin | Name | Netz / Beschaltung |
|---:|---|---|
| 1 | IN | `+5V_RAW`; 100 nF + 10 uF nach GND |
| 2 | GND | GND |
| 3 | EN | `AUX5_EN`; 100 kOhm Pulldown nach GND |
| 4 | FAULT | `AUX5_FAULT_N`; 100 kOhm Pull-up nach +3V3 |
| 5 | ILIM | 60.4 kOhm, 1 %, nach GND |
| 6 | OUT | `+5V_AUX`; 100 nF + 10 uF nach GND |

Mit den TI-Grenzgleichungen:

```text
R_nom = 60.4 kOhm, R_low = 59.796 kOhm, R_high = 61.004 kOhm
I_OS,max = 22980 / R_low^0.94 = 491 mA
I_OS,nom = 23950 / R_nom^0.977 = 436 mA
I_OS,min = 25230 / R_high^1.016 = 387 mA
```

Diese Dimensionierung garantiert rechnerisch weniger als 500 mA, liefert
aber typisch nur rund 436 mA. Falls stattdessen "500 mA nominal" gewünscht
wird, wären etwa 52.3 kOhm nötig; dann kann die obere Stromgrenze ungefähr
562 mA erreichen. Für den als 500-mA-Maximum beschrifteten Header bleibt
60.4 kOhm die festgelegte Variante.

Die +5-V-Ausgabe liegt nur auf einem Header-Pin. Daneben mindestens zwei
GND-Pins vorsehen. Auf dem Silkscreen: `5V OUT, <=0.5A, NOT INPUT`.

## 9. Fertigungs- und Footprint-Matrix

| Ref | Bestellteil | Gehäuse | KiCad / Footprint-Quelle | Bestückung |
|---|---|---|---|---|
| J1 | HRO TYPE-C-31-M-12 | Hybrid SMD/THT | stock HRO footprint | JLC oder Hand |
| U16 | USBLC6-4SC6Y | SOT-23-6L | SOT-23-6 | JLC, Hand-Rework möglich |
| U5 | BQ24074RGTR | RGT VQFN-16-EP 3x3 P0.5 | stock ThermalVias footprint | JLC only |
| U14 | BQ29700DSER | DSE WSON-6 1.5x1.5 P0.5 | stock WSON-6 | JLC only |
| Q2/Q3 | CSD16406Q3 | DQG VSON-CLIP 3.3x3.3 | stock NexFET footprint | JLC only |
| U8 | MAX17048G+T10 | TDFN-8-EP 2x2 P0.5 | stock TDFN footprint | JLC only |
| U6 | TPS63070RNMR | RNM VQFN-HR-15 3x2.5 | **custom nach MPQF446A** | JLC only |
| U7 | TPS61023DRLR | DRL SOT-563-6 | stock SOT-563 | JLC only |
| U15 | TPS2553DBVR | DBV SOT-23-6 | stock SOT-23-6 | JLC, Hand-Rework möglich |
| L6 | XFL4020-152MEC | 4.0x4.0x2.1 | `PocketLab_Custom:Coilcraft_XFL4020` | JLC |
| L7 | HBME042A-1R0MS-99 | 4.1x4.1x2.1 | `PocketLab_Custom:Cyntec_HBME042A` | JLC |

Allgemeine Widerstände und Kondensatoren bleiben 0805. Nur die beiden von TI
vorgesehenen TPS63070-HF-Bypässe C123/C124 und C113 dürfen 0603 sein; C113 kann auch
0805 werden, wenn ein geeignetes C0G-Teil verfügbar ist. Polaritätsmarkierungen für D101, J4, U5, U6, U7, U8 und U14 müssen
auf Fab und Silkscreen sichtbar sein. Der Akku-Plus-Pin erhält zusätzlich ein
großes `+` im Silkscreen.

## 10. Layoutregeln

1. Power-Pfad `CELL_POS -> BQ24074 BAT` und `CELL_NEG -> FETs -> GND` breit
   und kurz führen; keine Thermals an den Hochstrompads.
2. BQ29700, RC-Filter und beide MOSFETs bilden eine kompakte Insel direkt am
   Akkustecker. V- als Kelvin-Sense nach `PACK_NEG` führen.
3. Die vier Schaltknoten L1/L2 des TPS63070 und SW des TPS61023 so klein wie
   möglich halten; keine Signale oder Kupferflächen direkt darunter.
4. Beide Wandler erhalten eigene lokale Eingangskeramiken und eine kurze,
   niederinduktive PGND-Rückführung.
5. FB-Leitungen nicht unter Induktoren oder an Schaltknoten entlangführen.
6. BQ24074-EP an zusammenhängende GND-Fläche mit Thermal-Vias; keine
   Plane-Splits unter dem IC.
7. U16 und D101 direkt am Stecker platzieren. ESD-Rückweg darf
   nicht durch die digitale Masseinsel laufen.
8. Bestückte Testpunkte: TP101 `CELL_POS`, TP102 `CELL_NEG`, TP103
   `BAT_FET_MID`, TP104 GND, TP105 `VBUS_USB`, TP106 `VBUS_FUSED`, TP107
   `VSYS`, TP108 `+3V3`, TP109 `+5V_RAW` und TP110 `+5V_AUX`.
9. TP104 ist der gemeinsame GND-Testpunkt; lokale Masse-Probe-Pads dürfen beim
   Layout nahe kritischer Rails ergänzt werden, sofern der Platz reicht.
10. Schaltwandler und Induktoren maximal weit vom GNSS-Eingang, U.FL,
    NFC-Matching und Sub-GHz-RF-Pfad entfernt platzieren.

## 11. Bring-up und Abnahmekriterien

Vor Anschluss eines LiPos zuerst mit strombegrenztem Netzteil prüfen.
Der Zellensimulator muss gegenüber USB und Oszilloskopmasse potentialfrei
sein. Ein geerdeter Tastkopf gleichzeitig an `CELL_NEG` und System-GND würde
die Schutz-MOSFETs überbrücken und den Test ungültig beziehungsweise gefährlich
machen.

1. Widerstands-/Diodentest bei unbestücktem Akku: kein Kurzschluss zwischen
   `CELL_POS`, GND, 3V3 und 5V.
2. Labornetzteil als Zelle, 3.7 V und 100 mA Limit: korrekte Polarität,
   Ruhestrom und `VSYS` prüfen.
3. Unterspannungsabschaltung langsam durch 2.8 V fahren; Schutzereignis und
   Wiederanlauf dokumentieren. TPS63070-Kaltstart getrennt bei 2.8, 2.9 und
   3.0 V testen; unter 3.0 V ist der Start nicht garantiert.
4. USB bei abgestecktem Akku: Default USB100 messen. Per Firmware erst danach
   USB500 aktivieren.
5. Ladekennlinie bei 3.0-V-Zellensimulator prüfen: Vorladung, 500-mA-Ziel,
   CV-Regelung, etwa 51-mA-Terminierung und Timer.
6. U5-Thermografie im ungünstigsten linearen Ladefall durchführen.
7. 3V3 mit 0, 0.5, 1.0, 1.5 A sowie 2-A-Puls testen; Ripple, Start und
   Übergang bei VSYS 2.9 bis 4.5 V messen.
8. 5V mit 0, 0.5, 1.0 A sowie 1.5-A-Puls testen; Start/Stop und Überschwingen
   prüfen.
9. Headerlast langsam erhöhen: Mit 60.4 kOhm muss TPS2553 ungefähr zwischen
   0.387 und 0.491 A limitieren und `AUX5_FAULT_N` Low melden. Eine Messung
   außerhalb dieses Fensters deutet auf Bestückungs- oder Layoutfehler.
10. USB-Daten mit HS-Eye/Packet-Fehlerrate soweit verfügbar prüfen; mindestens
    Flash, CDC und längerer Datentransfer mit beiden Steckerorientierungen.
11. RF-Rauschvergleich mit allen Wandlerzuständen durchführen, besonders
    GNSS C/N0, Sub-GHz-Empfang und NFC-Lesereichweite.
12. Erst nach diesen Tests einen realen, geschützten 4.2-V-LiPo anschließen.

## 12. Offizielle Quellen

- TI BQ24074 Datenblatt: <https://www.ti.com/lit/ds/symlink/bq24074.pdf>
- TI TPS63070 Datenblatt: <https://www.ti.com/lit/ds/symlink/tps63070.pdf>
- TI RNM0015A Package Drawing: <https://www.ti.com/lit/ml/mpqf446a/mpqf446a.pdf>
- TI TPS61023 Datenblatt: <https://www.ti.com/lit/ds/symlink/tps61023.pdf>
- TI TPS61023EVM-052 User Guide: <https://www.ti.com/lit/ug/slvubp5/slvubp5.pdf>
- TI TPS2553 Datenblatt: <https://www.ti.com/lit/ds/symlink/tps2553.pdf>
- TI BQ2970-Familie: <https://www.ti.com/lit/ds/symlink/bq2970.pdf>
- TI BQ29700 EVM: <https://www.ti.com/lit/ug/sluuaz3/sluuaz3.pdf>
- TI CSD16406Q3 Datenblatt: <https://www.ti.com/lit/ds/symlink/csd16406q3.pdf>
- Analog Devices MAX17048/MAX17049: <https://www.analog.com/media/en/technical-documentation/data-sheets/max17048-max17049.pdf>
- ST USBLC6-4SC6Y: <https://www.st.com/resource/en/datasheet/usblc6-4sc6y.pdf>
- TI USB Type-C Engineer's Guide: <https://www.ti.com/lit/eb/slyy228/slyy228.pdf>
- USB-IF Type-C Cable and Connector Specification: <https://www.usb.org/usb-type-cr-cable-and-connector-specification>
- Littelfuse 1206L-Serie: <https://www.littelfuse.com/assetdocs/littelfuse-ptc-1206l-datasheet>
- Littelfuse SMF-Serie: <https://www.littelfuse.com/~/media/electronics/datasheets/tvs_diodes/littelfuse_tvs_diode_smf_datasheet.pdf.pdf>
- HRO TYPE-C-31-M-12: <https://en.krhro.com/Product-Details/726.html>
- JST PH-Serie: <https://www.jst.com/wp-content/uploads/2025/06/ePH.pdf>
- Espressif ESP32-S3 Hardware Design Guidelines: <https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html>
- Coilcraft XFL4020 Datenblatt: <https://www.coilcraft.com/getmedia/50632d43-da1b-4cdb-8ab4-3029cab51df3/xfl4020.pdf>
