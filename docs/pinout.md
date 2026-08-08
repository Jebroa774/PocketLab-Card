# ESP32-S3 pin allocation

This is the schematic-capture baseline. Changes must be reflected here and in
`firmware/include/board_pins.h`.

## Dedicated and reserved pins

| GPIO | Net / function | Direction | Notes |
|---:|---|---|---|
| 0 | BOOT_N | Input | Boot strap and physical boot button; not on expansion header |
| 3 | JTAG_STRAP_TP | Reserved | Test pad only; boot/JTAG strap |
| 5 | I2C_SDA | Bidirectional | Shared system I2C and expansion header |
| 6 | I2C_SCL | Output | Shared system I2C and expansion header |
| 7 | NFC_IRQ_N | Input | PN532 interrupt |
| 10 | RGB_DATA | Output | Four chained addressable LEDs |
| 11 | SPI_MOSI | Output | CC1101, microSD and expansion header |
| 12 | SPI_SCK | Output | CC1101, microSD and expansion header |
| 13 | SPI_MISO | Input | CC1101, microSD and expansion header |
| 14 | SUBGHZ_CS_N | Output | CC1101 chip select |
| 15 | SUBGHZ_GDO0 | Bidirectional | CC1101 packet/timing signal |
| 16 | SUBGHZ_GDO2 | Bidirectional | CC1101 carrier/timing signal |
| 17 | SD_CS_N | Output | microSD chip select |
| 18 | GNSS_TIMEPULSE | Input | GNSS PPS/timing input |
| 19 | USB_D_N | USB | Native USB; never use as expansion GPIO |
| 20 | USB_D_P | USB | Native USB; never use as expansion GPIO |
| 21 | GNSS_RX_FROM_MODULE | Input | Connected to MIA-M10Q TX |
| 26 | GNSS_TX_TO_MODULE | Output | Connected to MIA-M10Q RX |
| 33 | IOEXP_INT_N | Input | TCA9535 shared interrupt |
| 34 | BUZZER_PWM | Output | Buzzer MOSFET/PWM |
| 35 | IR_TX | Output | RMT carrier to IR MOSFET driver |
| 36 | IR_RX | Input | Demodulated IR receiver output |
| 43 | DEBUG_TX | Output | UART0 debug header |
| 44 | DEBUG_RX | Input | UART0 debug header |
| 45 | STRAP_VDD_SPI | Reserved | Test pad only; boot strap |
| 46 | STRAP_BOOT | Reserved | Test pad only; boot strap |

## Direct free GPIOs

These thirteen pins go directly to the 2.54 mm expansion header.

| GPIO | Useful hardware capability |
|---:|---|
| 1 | ADC1 channel 0, touch, digital, PWM |
| 2 | ADC1 channel 1, touch, digital, PWM |
| 4 | ADC1 channel 3, touch, digital, PWM |
| 8 | ADC1 channel 7, touch, digital, PWM |
| 9 | ADC1 channel 8, touch, digital, PWM |
| 37 | Digital, PWM, interrupt |
| 38 | Digital, PWM, interrupt |
| 39 | Digital, PWM, interrupt |
| 40 | Digital, PWM, interrupt |
| 41 | Digital, PWM, interrupt |
| 42 | Digital, PWM, interrupt |
| 47 | Digital, PWM, interrupt |
| 48 | Digital, PWM, interrupt |

All direct GPIOs are 3.3 V only and are not 5 V tolerant. Place optional
series-resistor footprints between the ESP32 and exposed header nets.

## TCA9535 internal allocation

| Expander pin | Function |
|---|---|
| P00 | NFC_RESET_N |
| P01 | GNSS_POWER_EN |
| P02 | BOOST5_EN |
| P03 | SD_DETECT_N |
| P04 | USER_BUTTON_A_N |
| P05 | USER_BUTTON_B_N |
| P06 | CHARGER_CHG_N |
| P07 | CHARGER_PGOOD_N |
| P10-P17 | EX0-EX7 on expansion header |

EX0-EX7 are 3.3 V digital I/O intended for switches, enables and other
low-speed signals. They do not provide ADC, accurate PWM, RMT or high-speed
protocol timing.

## J_EXT: 2 x 15, 2.54 mm expansion header

Use 1.0 mm finished plated holes. The header ships unpopulated and accepts
straight or right-angle male/female breakaway headers for Dupont cables.

| Pin | Net | Pin | Net |
|---:|---|---:|---|
| 1 | +3V3 | 2 | GND |
| 3 | GPIO1 / ADC | 4 | GPIO2 / ADC |
| 5 | GPIO4 / ADC | 6 | GPIO8 / ADC |
| 7 | GPIO9 / ADC | 8 | GPIO37 |
| 9 | GPIO38 | 10 | GPIO39 |
| 11 | GPIO40 | 12 | GPIO41 |
| 13 | GPIO42 | 14 | GPIO47 |
| 15 | GPIO48 | 16 | EX0 |
| 17 | EX1 | 18 | EX2 |
| 19 | EX3 | 20 | EX4 |
| 21 | EX5 | 22 | EX6 |
| 23 | EX7 | 24 | I2C_SDA |
| 25 | I2C_SCL | 26 | SPI_SCK |
| 27 | SPI_MOSI | 28 | SPI_MISO |
| 29 | +5V_AUX (protected) | 30 | GND |

Any direct free GPIO may be used as chip select for an external SPI device.
External I2C and SPI wiring shares the buses with onboard devices.

## J_DEBUG: 1 x 4, 2.54 mm

| Pin | Net |
|---:|---|
| 1 | GND |
| 2 | +3V3 |
| 3 | DEBUG_TX / GPIO43 |
| 4 | DEBUG_RX / GPIO44 |

## Connector labeling

Silkscreen must clearly distinguish:

- `GNSS ANT` and `SUB-GHz ANT` U.FL connectors
- `BAT +` and `BAT -` with explicit battery polarity
- `3V3 ONLY` beside direct GPIOs
- `5V AUX 500mA MAX` beside J_EXT pin 29
