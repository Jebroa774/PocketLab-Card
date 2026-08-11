# ESP32-S3 pin allocation

This is the schematic-capture baseline. Changes must be reflected here and in
`firmware/include/board_pins.h`.

## Dedicated and reserved pins

| GPIO | Net / function | Direction | Notes |
|---:|---|---|---|
| 0 | BOOT_N | Input | Boot strap and physical boot button; not on expansion header |
| 3 | JTAG_STRAP_TP | Reserved | Test pad only; boot/JTAG strap |
| 5 | I2C_SDA | Bidirectional | Shared system I2C and expansion header |
| 6 | I2C_SCL | Bidirectional | Shared system I2C and expansion header |
| 7 | NFC_IRQ_N | Input | PN532 interrupt |
| 9 | BOARD_TEMP_ADC | Analog input | Internal R736/RT701 divider; J5 pin 7 is probe-only |
| 10 | RGB_DATA | Output | Four chained addressable LEDs |
| 11 | SPI_MOSI | Output | CC1101, microSD and expansion header |
| 12 | SPI_SCK | Output | CC1101, microSD and expansion header |
| 13 | SPI_MISO | Input | CC1101, microSD and expansion header |
| 14 | SUBGHZ_CS_N | Output | CC1101 chip select |
| 15 | SUBGHZ_GDO0 | Bidirectional | CC1101 packet/timing signal |
| 16 | SUBGHZ_GDO2 | Bidirectional | CC1101 carrier/timing signal |
| 17 | SD_CS_N | Output | microSD chip select |
| 18 | LF_SCLK_3V3 | Output | HTRC110 serial clock through AHCT level shifter |
| 19 | USB_D_N | USB | Native USB; never use as expansion GPIO |
| 20 | USB_D_P | USB | Native USB; never use as expansion GPIO |
| 21 | LF_DOUT_3V3 | Input | HTRC110 data output through 5-V-tolerant LVC buffer |
| 35 | LF_DIN_3V3 | Output | HTRC110 serial/data input through AHCT level shifter |
| 36 | IR_TX | Output | RMT carrier to IR MOSFET driver |
| 37 | IR_RX | Input | Demodulated IR receiver output |
| 38 | PAIR_N | Input | Dedicated active-low physical app-pairing button; not exposed on J5 |
| 39 | IOEXP_INT_N | Input | Shared U9/U18 open-drain interrupt |
| 45 | STRAP_VDD_SPI | Reserved | Test pad only; boot strap |
| 46 | STRAP_BOOT | Reserved | Test pad only; boot strap |

## Direct free GPIOs

Eleven free pins reach J5 through fixed 100-ohm series resistors. R714 is the
twelfth branch but carries the reserved GPIO9 board-temperature node to a
probe-only header pad. GPIO38 is reserved for the dedicated PAIR button through
R606. GPIO43/44 can be used
as a normal UART pair; native USB CDC is
the default debug console.

| GPIO | Useful hardware capability |
|---:|---|
| 1 | ADC1 channel 0, touch, digital, PWM |
| 2 | ADC1 channel 1, touch, digital, PWM |
| 4 | ADC1 channel 3, touch, digital, PWM |
| 8 | ADC1 channel 7, touch, digital, PWM |
| 40 | Digital, PWM, interrupt |
| 41 | Digital, PWM, interrupt |
| 42 | Digital, PWM, interrupt |
| 43 | Digital, PWM, UART TX candidate |
| 44 | Digital, PWM, UART RX candidate |
| 47 | Digital, PWM, interrupt |
| 48 | Digital, PWM, interrupt |

All direct GPIOs are 3.3 V only and are not 5 V tolerant. The series resistors
limit edge rate and fault current but do not add level shifting or full ESD/
overvoltage protection. U24/U25 protect the five exposed I2C/SPI header nets;
the direct GPIO and EX0-EX7 pins remain series-protected only.

## U9 TCA9535 status and expansion allocation

U9 uses address `0x20` (A0/A1/A2 low). Its first eight ports monitor on-board
status/interrupt signals. Its second eight ports feed EX0-EX7 through 220-ohm
resistors R722-R729. All ports power up as inputs and U9 has no internal GPIO
pull resistors.

| Expander pin | Function |
|---|---|
| P00 | `SD_DETECT_N` |
| P01 | `CHARGER_CHG_N` |
| P02 | `CHARGER_PGOOD_N` |
| P03 | `AUX5_FAULT_N` |
| P04 | `FG_ALERT_N` |
| P05 | `BMI_INT1` |
| P06 | `BMI_INT2` |
| P07 | `USER_BUTTON_SELECT_N` (OK/SELECT) |
| P10-P17 | `EX0_INT`-`EX7_INT`, then 220 ohm to EX0-EX7 on J5 |

## U18 TCA9534 internal control allocation

U18 uses address `0x21` (A0 high, A1/A2 low). Its interrupt output shares
`IOEXP_INT_N` with U9. Hardware pull resistors define safe states before the
firmware configures the ports.

| Expander pin | Function |
|---|---|
| P0 | `BQ_EN1` |
| P1 | `CHG_DISABLE` |
| P2 | `AUX5_EN` |
| P3 | `NFC_RESET_N` |
| P4 | `LF_RFID_EN` |
| P5 | `BOOST5_EN` |
| P6 | `USER_BUTTON_A_N` (UP) |
| P7 | `USER_BUTTON_B_N` (DOWN) |

EX0-EX7 are 3.3 V digital I/O intended for switches, enables and other
low-speed signals. They do not provide ADC, accurate PWM, RMT or high-speed
protocol timing.

## J5: 6 x 5, 2.54 mm Dupont matrix

Use 1.0 mm finished plated holes. The matrix ships unpopulated and accepts
individual Dupont leads or short breakaway strips. A monolithic 2 x 15 housing
does not fit. Pad numbering is row-major as viewed from the front:

| Physical row | Pads and nets from left to right |
|---:|---|
| 1 | 1 `+3V3`, 2 `GND`, 3 `GPIO1/ADC`, 4 `GPIO2/ADC`, 5 `GPIO4/ADC`, 6 `GPIO8/ADC` |
| 2 | 7 `BOARD_TEMP probe`, 8 `GPIO40`, 9 `GPIO41`, 10 `GPIO42`, 11 `GPIO43/UART TX`, 12 `GPIO44/UART RX` |
| 3 | 13 `GPIO47`, 14 `GPIO48`, 15 `EX0`, 16 `EX1`, 17 `EX2`, 18 `EX3` |
| 4 | 19 `EX4`, 20 `EX5`, 21 `EX6`, 22 `EX7`, 23 `I2C_SDA`, 24 `I2C_SCL` |
| 5 | 25 `SPI_SCK`, 26 `SPI_MOSI`, 27 `SPI_MISO`, 28 `CHG_TS`, 29 `+5V_AUX`, 30 `GND` |

Any direct free GPIO may be used as chip select for an external SPI device.
J5 pin 7 is not a free GPIO: it is connected through R714 to the internal NTC
divider and must only be measured with a high-impedance 3.3-V-safe input.
External I2C and SPI wiring shares the buses with onboard devices. R730/R731
add 100 ohm in series to the exposed I2C header pair, and R732-R734 do the same
for SPI SCK/MOSI/MISO. U24 and U25 add 3.3-V-referenced shunt ESD protection on
the connector side of those five resistors. The single board-wide I2C pull-up
pair is 3.3 kohm.
For an external 10-kohm battery NTC, cut SJ1 and connect the NTC between J5
pins 28 and 30. Do not connect a raw cell directly to pin 28.

## Connector labeling

Silkscreen must clearly distinguish:

- `LF COIL` beside J3 and `868 ANT` beside the spring pad
- `BAT +` and `BAT -` with explicit battery polarity
- `3V3 ONLY` beside direct GPIOs
- `5V AUX 500mA MAX` beside J5 pin 29
- `PAIR` beside SW6
