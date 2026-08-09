#pragma once

#include <Arduino.h>

#ifndef POCKETLAB_ALLOW_SUBGHZ_TX
#define POCKETLAB_ALLOW_SUBGHZ_TX 0
#endif

#ifndef POCKETLAB_ALLOW_IR_TX
#define POCKETLAB_ALLOW_IR_TX 0
#endif

#ifndef POCKETLAB_ALLOW_GPIO_OUTPUT
#define POCKETLAB_ALLOW_GPIO_OUTPUT 0
#endif

namespace pocketlab::config {

inline constexpr char FIRMWARE_NAME[] = "PocketLab Card";
inline constexpr char FIRMWARE_VERSION[] = "0.3.0-dev";
inline constexpr char HOSTNAME[] = "pocketlab-card";

inline constexpr uint16_t HTTP_PORT = 80;
inline constexpr uint16_t WEBSOCKET_PORT = 81;
inline constexpr uint8_t WIFI_CHANNEL = 6;
inline constexpr uint8_t WIFI_MAX_CLIENTS = 4;

inline constexpr uint32_t I2C_FREQUENCY_HZ = 400000;
inline constexpr uint8_t TCA9535_STATUS_ADDRESS = 0x20;
inline constexpr uint8_t TCA9534_CONTROL_ADDRESS = 0x21;
inline constexpr uint8_t PN532_I2C_ADDRESS = 0x24;

inline constexpr uint32_t SPI_FREQUENCY_HZ = 8000000;
inline constexpr uint32_t SD_FREQUENCY_HZ = 20000000;
inline constexpr uint32_t GNSS_BAUD = 9600;
inline constexpr uint32_t GNSS_FIX_TIMEOUT_MS = 3500;
inline constexpr uint32_t TRIP_LOG_INTERVAL_MS = 1000;
inline constexpr uint32_t TRIP_FLUSH_INTERVAL_MS = 5000;

inline constexpr size_t MAX_NMEA_LINE_LENGTH = 127;
inline constexpr size_t MAX_FILE_PATH_LENGTH = 96;
inline constexpr size_t MAX_DIRECTORY_ENTRIES = 100;

inline constexpr bool SUBGHZ_TX_COMPILED = POCKETLAB_ALLOW_SUBGHZ_TX != 0;
inline constexpr bool IR_TX_COMPILED = POCKETLAB_ALLOW_IR_TX != 0;
inline constexpr bool GPIO_OUTPUT_COMPILED = POCKETLAB_ALLOW_GPIO_OUTPUT != 0;

}  // namespace pocketlab::config
