#include "hardware_manager.h"

#include <cmath>

#include "board_pins.h"
#include "firmware_config.h"
#include "json_util.h"

namespace pocketlab {
namespace {

constexpr uint8_t TCA9535_INPUT_PORT_0 = 0x00;
constexpr uint8_t TCA9535_INPUT_PORT_1 = 0x01;
constexpr uint8_t TCA9535_OUTPUT_PORT_0 = 0x02;
constexpr uint8_t TCA9535_OUTPUT_PORT_1 = 0x03;
constexpr uint8_t TCA9535_POLARITY_PORT_0 = 0x04;
constexpr uint8_t TCA9535_POLARITY_PORT_1 = 0x05;
constexpr uint8_t TCA9535_CONFIG_PORT_0 = 0x06;
constexpr uint8_t TCA9535_CONFIG_PORT_1 = 0x07;

constexpr uint8_t TCA9534_INPUT_PORT = 0x00;
constexpr uint8_t TCA9534_OUTPUT_PORT = 0x01;
constexpr uint8_t TCA9534_POLARITY_PORT = 0x02;
constexpr uint8_t TCA9534_CONFIG_PORT = 0x03;
constexpr uint8_t TCA9534_CONTROL_INPUT_MASK = 0xC0;

constexpr uint8_t CC1101_PARTNUM = 0x30;
constexpr uint8_t CC1101_VERSION = 0x31;
constexpr uint8_t CC1101_READ_BURST = 0xC0;

bool isDirectExpansionPin(uint8_t gpio) {
  for (const uint8_t candidate : pins::DIRECT_EXPANSION) {
    if (candidate == gpio) return true;
  }
  return false;
}

}  // namespace

void HardwareManager::setSafeOutput(uint8_t pin, uint8_t level) {
  digitalWrite(pin, level);
  pinMode(pin, OUTPUT);
}

void HardwareManager::begin() {
  // Inactive levels are established before switching the pads to outputs.
  setSafeOutput(pins::SUBGHZ_CS_N, HIGH);
  setSafeOutput(pins::SD_CS_N, HIGH);
  setSafeOutput(pins::IR_TX, LOW);
  setSafeOutput(pins::RGB_DATA, LOW);
  setSafeOutput(pins::LF_SCLK, HIGH);
  setSafeOutput(pins::LF_DIN, LOW);

  pinMode(pins::NFC_IRQ_N, INPUT_PULLUP);
  pinMode(pins::SUBGHZ_GDO0, INPUT);
  pinMode(pins::SUBGHZ_GDO2, INPUT);
  pinMode(pins::LF_DOUT, INPUT);
  pinMode(pins::PAIR_N, INPUT_PULLUP);
  pinMode(pins::IR_RX, INPUT_PULLUP);
  pinMode(pins::IOEXP_INT_N, INPUT_PULLUP);
  pinMode(pins::BOARD_TEMP_ADC, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(pins::BOARD_TEMP_ADC, ADC_11db);

  // Expansion pins never become outputs unless a future, separately audited
  // firmware build explicitly enables that capability.
  for (const uint8_t gpio : pins::DIRECT_EXPANSION) {
    pinMode(gpio, INPUT);
  }

  Wire.begin(pins::I2C_SDA, pins::I2C_SCL, config::I2C_FREQUENCY_HZ);
  SPI.begin(pins::SPI_SCK, pins::SPI_MISO, pins::SPI_MOSI);

  status_.statusExpanderPresent = configureStatusExpander();
  status_.controlExpanderPresent = configureControlExpander();
  if (status_.controlExpanderPresent) {
    // U18 is configured with every controlled rail disabled and PN532 held in
    // reset. Releasing reset here only boots PN532; no RF command is issued.
    delay(10);
    if (setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::NfcResetN), true)) {
      delay(20);
      updateControlExpanderInputs();
    }
  }
  if (status_.statusExpanderPresent) updateStatusExpanderInputs();

  status_.nfcResponding = probeI2cAddress(config::PN532_I2C_ADDRESS);
  status_.secureElementPresent = probeSecureElement();
  status_.pairButtonPressed = digitalRead(pins::PAIR_N) == LOW;
  updateBoardTemperature();
  probeSubGhz();
  lastPollMs_ = millis();
}

void HardwareManager::poll() {
  const uint32_t now = millis();
  if (now - lastPollMs_ < 2000) return;
  lastPollMs_ = now;

  if (status_.statusExpanderPresent) updateStatusExpanderInputs();
  if (status_.controlExpanderPresent) updateControlExpanderInputs();
  status_.nfcResponding = probeI2cAddress(config::PN532_I2C_ADDRESS);
  status_.pairButtonPressed = digitalRead(pins::PAIR_N) == LOW;
  updateBoardTemperature();
  status_.pairingWindowOpen = pairingWindowUntilMs_ != 0 &&
                              static_cast<int32_t>(pairingWindowUntilMs_ - now) > 0;
  if (!status_.pairingWindowOpen) pairingWindowUntilMs_ = 0;
}

bool HardwareManager::probeI2cAddress(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission(true) == 0;
}

bool HardwareManager::configureStatusExpander() {
  if (!probeI2cAddress(config::TCA9535_STATUS_ADDRESS)) return false;

  // U9 is strictly input-only: eight internal status lines and EX0..EX7.
  // Explicit polarity and output-latch values make later diagnostics
  // deterministic without ever changing a pin to output mode.
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_OUTPUT_PORT_0, 0x00)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_OUTPUT_PORT_1, 0x00)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_POLARITY_PORT_0, 0x00)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_POLARITY_PORT_1, 0x00)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_CONFIG_PORT_0, 0xFF)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_CONFIG_PORT_1, 0xFF)) {
    return false;
  }
  return true;
}

bool HardwareManager::configureControlExpander() {
  if (!probeI2cAddress(config::TCA9534_CONTROL_ADDRESS)) return false;

  // Write the safe latch before enabling outputs: charger stays in USB100
  // mode, charging remains enabled, AUX 5 V/LF RFID/boost stay off, and PN532 is
  // held in reset. P6/P7 remain inputs for the active-low user buttons.
  controlOutputs_ = 0x00;
  if (!writeI2cRegister(config::TCA9534_CONTROL_ADDRESS, TCA9534_OUTPUT_PORT,
                        controlOutputs_)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9534_CONTROL_ADDRESS, TCA9534_POLARITY_PORT, 0x00)) {
    return false;
  }
  if (!writeI2cRegister(config::TCA9534_CONTROL_ADDRESS, TCA9534_CONFIG_PORT,
                        TCA9534_CONTROL_INPUT_MASK)) {
    return false;
  }

  status_.chargerUsb100Mode = true;
  status_.chargerDisabled = false;
  status_.aux5Enabled = false;
  status_.nfcResetReleased = false;
  status_.lfRfidPowerEnabled = false;
  status_.lfRfidTransportOk = false;
  status_.lfAntennaFail = true;
  status_.boost5Enabled = false;
  return true;
}

bool HardwareManager::writeI2cRegister(uint8_t address, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission(true) == 0;
}

bool HardwareManager::readI2cRegister(uint8_t address, uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(address, static_cast<uint8_t>(1)) != 1) return false;
  value = Wire.read();
  return true;
}

bool HardwareManager::setControlOutput(uint8_t bit, bool high) {
  if (!status_.controlExpanderPresent || bit > 5) return false;

  const uint8_t mask = static_cast<uint8_t>(1U << bit);
  const uint8_t next = high ? (controlOutputs_ | mask) : (controlOutputs_ & ~mask);
  if (!writeI2cRegister(config::TCA9534_CONTROL_ADDRESS, TCA9534_OUTPUT_PORT, next)) {
    status_.controlExpanderPresent = false;
    return false;
  }
  controlOutputs_ = next;

  if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::ChargerUsbModeEn1)) {
    status_.chargerUsb100Mode = !high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::ChargerDisable)) {
    status_.chargerDisabled = high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::Aux5Enable)) {
    status_.aux5Enabled = high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::NfcResetN)) {
    status_.nfcResetReleased = high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::LfRfidPowerEnable)) {
    status_.lfRfidPowerEnabled = high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::Boost5Enable)) {
    status_.boost5Enabled = high;
  }
  return true;
}

bool HardwareManager::probeSecureElement() {
  // ATECC608C normally sleeps and therefore does not ACK a plain address
  // probe. Its documented wake token is an all-zero byte at 100 kHz.
  Wire.setClock(100000);
  Wire.beginTransmission(0x00);
  Wire.endTransmission(true);
  delay(3);
  const bool present = probeI2cAddress(config::ATECC608C_I2C_ADDRESS);
  if (present) {
    Wire.beginTransmission(config::ATECC608C_I2C_ADDRESS);
    Wire.write(0x01);  // Sleep word address; no configuration is changed.
    Wire.endTransmission(true);
  }
  Wire.setClock(config::I2C_FREQUENCY_HZ);
  return present;
}

void HardwareManager::htrcInitializeInterface() {
  digitalWrite(pins::LF_DIN, LOW);
  digitalWrite(pins::LF_SCLK, HIGH);
  delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
  digitalWrite(pins::LF_DIN, HIGH);
  delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
}

void HardwareManager::htrcWriteBits(uint8_t value, uint8_t count) {
  for (int8_t bit = static_cast<int8_t>(count) - 1; bit >= 0; --bit) {
    digitalWrite(pins::LF_SCLK, LOW);
    digitalWrite(pins::LF_DIN, (value & (1U << bit)) != 0 ? HIGH : LOW);
    delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
    digitalWrite(pins::LF_SCLK, HIGH);
    delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
  }
}

void HardwareManager::htrcCommand(uint8_t command) {
  noInterrupts();
  htrcInitializeInterface();
  htrcWriteBits(command, 8);
  interrupts();
}

uint8_t HardwareManager::htrcCommandWithResponse(uint8_t command) {
  uint8_t response = 0;
  noInterrupts();
  htrcInitializeInterface();
  htrcWriteBits(command, 8);
  digitalWrite(pins::LF_DIN, LOW);
  for (uint8_t bit = 0; bit < 8; ++bit) {
    digitalWrite(pins::LF_SCLK, LOW);
    delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
    digitalWrite(pins::LF_SCLK, HIGH);
    delayMicroseconds(config::LF_SERIAL_HALF_PERIOD_US);
    response = static_cast<uint8_t>((response << 1) |
                                    (digitalRead(pins::LF_DOUT) == HIGH ? 1U : 0U));
  }
  interrupts();
  return response;
}

bool HardwareManager::configureHtrc110() {
  // 4 MHz external clock, smart comparator and LP1 enabled. Page 0 uses the
  // 6-kHz/160-Hz filters and high gain; page 1 enables the antenna bridge.
  htrcCommand(0x70);
  htrcCommand(0x4B);
  htrcCommand(0x50);
  htrcCommand(0x60);
  delay(5);

  const uint8_t page0 = htrcCommandWithResponse(0x04);
  const uint8_t page1 = htrcCommandWithResponse(0x05);
  const uint8_t page3 = htrcCommandWithResponse(0x07);
  if ((page0 & 0x0F) != 0x0B || (page1 & 0x0F) != 0x00 ||
      (page3 & 0x0F) != 0x00) {
    status_.lfRfidTransportOk = false;
    return false;
  }

  status_.lfPhase = static_cast<uint8_t>(htrcCommandWithResponse(0x08) & 0x3F);
  status_.lfSamplingTime =
      static_cast<uint8_t>(((status_.lfPhase << 1) + 0x3F) & 0x3F);
  htrcCommand(static_cast<uint8_t>(0x80 | status_.lfSamplingTime));
  const uint8_t sampling = htrcCommandWithResponse(0x02) & 0x3F;
  const uint8_t page2 = htrcCommandWithResponse(0x06);
  status_.lfAntennaFail = (page2 & 0x10) != 0;
  status_.lfRfidTransportOk = sampling == status_.lfSamplingTime;
  return status_.lfRfidTransportOk;
}

bool HardwareManager::setLfRfidPower(bool enabled) {
  if (enabled && status_.boardOverTemperature) return false;
  if (enabled == status_.lfRfidPowerEnabled) {
    return !enabled || configureHtrc110();
  }
  if (enabled) {
    if (!status_.boost5Enabled) {
      if (!setBoost5(true)) return false;
      lfOwnsBoost_ = true;
      delay(3);
    }
    if (!setControlOutput(
            static_cast<uint8_t>(pins::ControlExpanderPin::LfRfidPowerEnable), true)) {
      if (lfOwnsBoost_) setBoost5(false);
      lfOwnsBoost_ = false;
      return false;
    }
    delay(config::LF_POWER_SETTLE_MS);
    return configureHtrc110();
  }

  if (!setControlOutput(
          static_cast<uint8_t>(pins::ControlExpanderPin::LfRfidPowerEnable), false)) {
    return false;
  }
  status_.lfRfidTransportOk = false;
  status_.lfAntennaFail = true;
  status_.lfPhase = 0xFF;
  status_.lfSamplingTime = 0xFF;
  if (lfOwnsBoost_) {
    lfOwnsBoost_ = false;
    return setBoost5(false);
  }
  return true;
}

bool HardwareManager::diagnoseLfRfid() {
  return status_.lfRfidPowerEnabled && configureHtrc110();
}

bool HardwareManager::armPairingWindow() {
  status_.pairButtonPressed = digitalRead(pins::PAIR_N) == LOW;
  if (!status_.pairButtonPressed || !status_.secureElementPresent) return false;
  pairingWindowUntilMs_ = millis() + config::PAIRING_WINDOW_MS;
  status_.pairingWindowOpen = true;
  return true;
}

bool HardwareManager::setBoost5(bool enabled) {
  if (enabled && status_.boardOverTemperature) return false;
  if (!enabled && status_.lfRfidPowerEnabled) return false;
  if (!setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::Boost5Enable),
                        enabled)) {
    return false;
  }
  return true;
}

void HardwareManager::sendIrMark(uint32_t durationUs) {
  // A bounded software carrier avoids another dependency and is adequate for
  // NEC bring-up. The 13 us half-period is approximately 38.5 kHz.
  const uint32_t started = micros();
  while (static_cast<uint32_t>(micros() - started) < durationUs) {
    digitalWrite(pins::IR_TX, HIGH);
    delayMicroseconds(13);
    digitalWrite(pins::IR_TX, LOW);
    delayMicroseconds(13);
  }
  digitalWrite(pins::IR_TX, LOW);
}

void HardwareManager::sendIrSpace(uint32_t durationUs) {
  digitalWrite(pins::IR_TX, LOW);
  delayMicroseconds(durationUs);
}

void HardwareManager::sendIrByteLsb(uint8_t value) {
  for (uint8_t bit = 0; bit < 8; ++bit) {
    sendIrMark(560);
    sendIrSpace((value & (1U << bit)) != 0 ? 1690 : 560);
  }
}

bool HardwareManager::sendIrNec(uint8_t address, uint8_t command, uint8_t repeats) {
  if (!config::IR_TX_COMPILED || repeats > 2 || status_.boardOverTemperature) {
    return false;
  }

  const uint32_t now = millis();
  if (lastIrTxMs_ != 0 && static_cast<uint32_t>(now - lastIrTxMs_) < 150) {
    return false;
  }

  const bool restoreBoostOff = !status_.boost5Enabled;
  if (restoreBoostOff) {
    if (!setBoost5(true)) return false;
    delay(3);
  }

  sendIrMark(9000);
  sendIrSpace(4500);
  sendIrByteLsb(address);
  sendIrByteLsb(static_cast<uint8_t>(~address));
  sendIrByteLsb(command);
  sendIrByteLsb(static_cast<uint8_t>(~command));
  sendIrMark(560);

  for (uint8_t repeat = 0; repeat < repeats; ++repeat) {
    delay(40);
    sendIrMark(9000);
    sendIrSpace(2250);
    sendIrMark(560);
  }
  digitalWrite(pins::IR_TX, LOW);
  lastIrTxMs_ = millis();

  if (restoreBoostOff) {
    delay(1);
    if (!setBoost5(false)) return false;
  }
  return true;
}

void HardwareManager::updateStatusExpanderInputs() {
  uint8_t port0 = 0xFF;
  uint8_t port1 = 0xFF;
  if (!readI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_INPUT_PORT_0, port0) ||
      !readI2cRegister(config::TCA9535_STATUS_ADDRESS, TCA9535_INPUT_PORT_1, port1)) {
    status_.statusExpanderPresent = false;
    return;
  }

  status_.statusInputs0 = port0;
  status_.expansionInputs = port1;
  status_.sdDetected =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::SdDetectN))) == 0;
  status_.chargerActive =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::ChargerN))) == 0;
  status_.externalPowerGood =
      (port0 &
       (1U << static_cast<uint8_t>(pins::StatusExpanderPin::ChargerPowerGoodN))) == 0;
  status_.aux5FaultActive =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::Aux5FaultN))) == 0;
  status_.fuelGaugeAlertActive =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::FuelGaugeAlertN))) == 0;
  status_.bmiInt1 =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::BmiInt1))) != 0;
  status_.bmiInt2 =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::BmiInt2))) != 0;
  status_.bmpInt =
      (port0 & (1U << static_cast<uint8_t>(pins::StatusExpanderPin::BmpInt))) != 0;
}

void HardwareManager::updateControlExpanderInputs() {
  uint8_t input = 0xFF;
  if (!readI2cRegister(config::TCA9534_CONTROL_ADDRESS, TCA9534_INPUT_PORT, input)) {
    status_.controlExpanderPresent = false;
    return;
  }
  status_.controlInputs = input;
  status_.userButtonAPressed =
      (input & (1U << static_cast<uint8_t>(pins::ControlExpanderPin::UserButtonAN))) == 0;
  status_.userButtonBPressed =
      (input & (1U << static_cast<uint8_t>(pins::ControlExpanderPin::UserButtonBN))) == 0;
}

void HardwareManager::updateBoardTemperature() {
  constexpr uint8_t SAMPLE_COUNT = 16;
  uint32_t sumMillivolts = 0;
  for (uint8_t sample = 0; sample < SAMPLE_COUNT; ++sample) {
    sumMillivolts += analogReadMilliVolts(pins::BOARD_TEMP_ADC);
  }
  const float millivolts = static_cast<float>(sumMillivolts) / SAMPLE_COUNT;

  // Near-rail readings indicate an open/shorted divider and are reported as
  // invalid instead of producing a misleading extreme temperature.
  if (millivolts < 20.0F || millivolts > config::BOARD_TEMP_DIVIDER_MV - 20.0F) {
    status_.boardTemperatureValid = false;
    status_.boardOverTemperature = true;
    enforceThermalShutdown();
    return;
  }

  const float ntcOhms = config::BOARD_TEMP_DIVIDER_OHMS * millivolts /
                         (config::BOARD_TEMP_DIVIDER_MV - millivolts);
  constexpr float NOMINAL_KELVIN = 25.0F + 273.15F;
  const float inverseKelvin =
      (1.0F / NOMINAL_KELVIN) +
      (std::log(ntcOhms / config::BOARD_TEMP_NOMINAL_OHMS) /
       config::BOARD_TEMP_BETA);
  const float celsius = (1.0F / inverseKelvin) - 273.15F;
  if (!std::isfinite(celsius) || celsius < -40.0F || celsius > 125.0F) {
    status_.boardTemperatureValid = false;
    status_.boardOverTemperature = true;
    enforceThermalShutdown();
    return;
  }

  status_.boardTemperatureC = celsius;
  status_.boardTemperatureValid = true;
  if (celsius >= config::BOARD_TEMP_SHUTDOWN_C) {
    status_.boardOverTemperature = true;
  } else if (celsius <= config::BOARD_TEMP_RELEASE_C) {
    status_.boardOverTemperature = false;
  }

  if (status_.boardOverTemperature) {
    enforceThermalShutdown();
  } else if (status_.chargerDisabled && status_.controlExpanderPresent) {
    // Only the thermal policy currently asserts CHG_DISABLE. Rails are not
    // automatically re-enabled after cooling; the app must request them.
    setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::ChargerDisable),
                     false);
  }
}

void HardwareManager::enforceThermalShutdown() {
  digitalWrite(pins::IR_TX, LOW);
  if (!status_.controlExpanderPresent) return;
  if (status_.lfRfidPowerEnabled) setLfRfidPower(false);
  setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::Aux5Enable), false);
  if (status_.boost5Enabled) setBoost5(false);
  setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::ChargerDisable), true);
}

uint8_t HardwareManager::readCc1101StatusRegister(uint8_t address) {
  SPI.beginTransaction(SPISettings(config::SPI_FREQUENCY_HZ, MSBFIRST, SPI_MODE0));
  digitalWrite(pins::SUBGHZ_CS_N, LOW);

  const uint32_t started = micros();
  while (digitalRead(pins::SPI_MISO) == HIGH) {
    if (micros() - started > 2000) {
      digitalWrite(pins::SUBGHZ_CS_N, HIGH);
      SPI.endTransaction();
      return 0xFF;
    }
  }

  SPI.transfer(static_cast<uint8_t>(address | CC1101_READ_BURST));
  const uint8_t value = SPI.transfer(0x00);
  digitalWrite(pins::SUBGHZ_CS_N, HIGH);
  SPI.endTransaction();
  return value;
}

void HardwareManager::probeSubGhz() {
  status_.cc1101PartNumber = readCc1101StatusRegister(CC1101_PARTNUM);
  status_.cc1101Version = readCc1101StatusRegister(CC1101_VERSION);
  status_.subGhzResponding = status_.cc1101PartNumber == 0x00 &&
                            status_.cc1101Version != 0x00 &&
                            status_.cc1101Version != 0xFF;
}

bool HardwareManager::readDirectGpio(uint8_t gpio, bool &level) const {
  if (!isDirectExpansionPin(gpio)) return false;
  level = digitalRead(gpio) != LOW;
  return true;
}

String HardwareManager::statusJson() const {
  String result;
  result.reserve(1000);
  result += F("{\"ioExpander\":");
  result += json::boolean(status_.statusExpanderPresent && status_.controlExpanderPresent);
  result += F(",\"ioExpanders\":{\"statusTca9535\":");
  result += json::boolean(status_.statusExpanderPresent);
  result += F(",\"controlTca9534\":");
  result += json::boolean(status_.controlExpanderPresent);
  result += F(",\"statusInputs0\":");
  result += static_cast<unsigned>(status_.statusInputs0);
  result += F(",\"expansionInputs\":");
  result += static_cast<unsigned>(status_.expansionInputs);
  result += F(",\"controlInputs\":");
  result += static_cast<unsigned>(status_.controlInputs);
  result += '}';
  result += F(",\"nfc\":");
  result += json::boolean(status_.nfcResponding);
  result += F(",\"nfcResetReleased\":");
  result += json::boolean(status_.nfcResetReleased);
  result += F(",\"subGhz\":");
  result += json::boolean(status_.subGhzResponding);
  result += F(",\"cc1101Part\":");
  result += static_cast<unsigned>(status_.cc1101PartNumber);
  result += F(",\"cc1101Version\":");
  result += static_cast<unsigned>(status_.cc1101Version);
  result += F(",\"lfRfid\":{\"power\":");
  result += json::boolean(status_.lfRfidPowerEnabled);
  result += F(",\"transport\":");
  result += json::boolean(status_.lfRfidTransportOk);
  result += F(",\"antennaFail\":");
  result += json::boolean(status_.lfAntennaFail);
  result += F(",\"phase\":");
  result += static_cast<unsigned>(status_.lfPhase);
  result += F(",\"samplingTime\":");
  result += static_cast<unsigned>(status_.lfSamplingTime);
  result += '}';
  result += F(",\"security\":{\"atecc608c\":");
  result += json::boolean(status_.secureElementPresent);
  result += F(",\"pairButton\":");
  result += json::boolean(status_.pairButtonPressed);
  result += F(",\"pairingWindow\":");
  result += json::boolean(status_.pairingWindowOpen);
  result += F(",\"provisioned\":false}");
  result += F(",\"boost5\":");
  result += json::boolean(status_.boost5Enabled);
  result += F(",\"aux5\":");
  result += json::boolean(status_.aux5Enabled);
  result += F(",\"chargerUsb100Mode\":");
  result += json::boolean(status_.chargerUsb100Mode);
  result += F(",\"chargerDisabled\":");
  result += json::boolean(status_.chargerDisabled);
  result += F(",\"sdDetected\":");
  result += json::boolean(status_.sdDetected);
  result += F(",\"chargerActive\":");
  result += json::boolean(status_.chargerActive);
  result += F(",\"externalPowerGood\":");
  result += json::boolean(status_.externalPowerGood);
  result += F(",\"aux5Fault\":");
  result += json::boolean(status_.aux5FaultActive);
  result += F(",\"fuelGaugeAlert\":");
  result += json::boolean(status_.fuelGaugeAlertActive);
  result += F(",\"sensorInterrupts\":{\"bmi1\":");
  result += json::boolean(status_.bmiInt1);
  result += F(",\"bmi2\":");
  result += json::boolean(status_.bmiInt2);
  result += F(",\"bmp\":");
  result += json::boolean(status_.bmpInt);
  result += F("},\"buttons\":{\"a\":");
  result += json::boolean(status_.userButtonAPressed);
  result += F(",\"b\":");
  result += json::boolean(status_.userButtonBPressed);
  result += '}';
  result += F(",\"boardTemperature\":{\"valid\":");
  result += json::boolean(status_.boardTemperatureValid);
  result += F(",\"celsius\":");
  if (status_.boardTemperatureValid) {
    result += String(status_.boardTemperatureC, 1);
  } else {
    result += F("null");
  }
  result += F(",\"overTemperature\":");
  result += json::boolean(status_.boardOverTemperature);
  result += '}';
  result += F(",\"txPolicy\":{\"subGhz\":");
  result += json::boolean(config::SUBGHZ_TX_COMPILED);
  result += F(",\"ir\":");
  result += json::boolean(config::IR_TX_COMPILED);
  result += F(",\"gpioOutput\":");
  result += json::boolean(config::GPIO_OUTPUT_COMPILED);
  result += F("}}");
  return result;
}

}  // namespace pocketlab
