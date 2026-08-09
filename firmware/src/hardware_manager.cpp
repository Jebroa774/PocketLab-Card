#include "hardware_manager.h"

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
  setSafeOutput(pins::BUZZER_PWM, LOW);
  setSafeOutput(pins::RGB_DATA, LOW);

  pinMode(pins::NFC_IRQ_N, INPUT_PULLUP);
  pinMode(pins::SUBGHZ_GDO0, INPUT);
  pinMode(pins::SUBGHZ_GDO2, INPUT);
  pinMode(pins::GNSS_TIMEPULSE, INPUT);
  pinMode(pins::IR_RX, INPUT_PULLUP);
  pinMode(pins::IOEXP_INT_N, INPUT_PULLUP);

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
  // mode, charging remains enabled, AUX 5 V/GNSS/boost stay off, and PN532 is
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
  status_.gnssPowerEnabled = false;
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
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::GnssPowerEnable)) {
    status_.gnssPowerEnabled = high;
  } else if (bit == static_cast<uint8_t>(pins::ControlExpanderPin::Boost5Enable)) {
    status_.boost5Enabled = high;
  }
  return true;
}

bool HardwareManager::setGnssPower(bool enabled) {
  if (!setControlOutput(
          static_cast<uint8_t>(pins::ControlExpanderPin::GnssPowerEnable), enabled)) {
    return false;
  }
  return true;
}

bool HardwareManager::setBoost5(bool enabled) {
  if (!setControlOutput(static_cast<uint8_t>(pins::ControlExpanderPin::Boost5Enable),
                        enabled)) {
    return false;
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
  result.reserve(900);
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
  result += F(",\"gnssPower\":");
  result += json::boolean(status_.gnssPowerEnabled);
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
