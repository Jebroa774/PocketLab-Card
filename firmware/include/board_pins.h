#pragma once

#include <stdint.h>

namespace pocketlab::pins {

// Boot and shared buses
inline constexpr uint8_t BOOT_N = 0;
inline constexpr uint8_t I2C_SDA = 5;
inline constexpr uint8_t I2C_SCL = 6;
inline constexpr uint8_t SPI_MOSI = 11;
inline constexpr uint8_t SPI_SCK = 12;
inline constexpr uint8_t SPI_MISO = 13;

// NFC
inline constexpr uint8_t NFC_IRQ_N = 7;

// LEDs
inline constexpr uint8_t RGB_DATA = 10;

// Sub-GHz
inline constexpr uint8_t SUBGHZ_CS_N = 14;
inline constexpr uint8_t SUBGHZ_GDO0 = 15;
inline constexpr uint8_t SUBGHZ_GDO2 = 16;

// Storage
inline constexpr uint8_t SD_CS_N = 17;

// 125-kHz LF RFID (HTRC110 through 3.3-V/5-V level translators)
inline constexpr uint8_t LF_SCLK = 18;
inline constexpr uint8_t LF_DOUT = 21;
inline constexpr uint8_t LF_DIN = 35;

// Dedicated physical app-pairing button
inline constexpr uint8_t PAIR_N = 38;

// Native USB
inline constexpr uint8_t USB_D_N = 19;
inline constexpr uint8_t USB_D_P = 20;

// I/O expander interrupt
inline constexpr uint8_t IOEXP_INT_N = 39;

// Infrared
inline constexpr uint8_t IR_TX = 36;
inline constexpr uint8_t IR_RX = 37;

// Internal 10-k NTC divider. J5 pin 7 is only a protected, high-impedance
// probe point for this node; GPIO9 must never be driven.
inline constexpr uint8_t BOARD_TEMP_ADC = 9;

// Direct expansion GPIOs
inline constexpr uint8_t DIRECT_EXPANSION[] = {
    1, 2, 4, 8, 40, 41, 42, 43, 44, 47, 48,
};

// U9 / TCA9535 at 0x20. Both ports remain inputs; P10-P17 are EX0-EX7.
enum class StatusExpanderPin : uint8_t {
  SdDetectN = 0,
  ChargerN = 1,
  ChargerPowerGoodN = 2,
  Aux5FaultN = 3,
  FuelGaugeAlertN = 4,
  BmiInt1 = 5,
  BmiInt2 = 6,
  BmpInt = 7,
  Ex0 = 8,
  Ex1 = 9,
  Ex2 = 10,
  Ex3 = 11,
  Ex4 = 12,
  Ex5 = 13,
  Ex6 = 14,
  Ex7 = 15,
};

// U18 / TCA9534 at 0x21. P0-P5 are outputs and P6-P7 are inputs.
enum class ControlExpanderPin : uint8_t {
  ChargerUsbModeEn1 = 0,
  ChargerDisable = 1,
  Aux5Enable = 2,
  NfcResetN = 3,
  LfRfidPowerEnable = 4,
  Boost5Enable = 5,
  UserButtonAN = 6,
  UserButtonBN = 7,
};

}  // namespace pocketlab::pins
