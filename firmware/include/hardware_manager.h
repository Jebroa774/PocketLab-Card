#pragma once

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>

namespace pocketlab {

struct HardwareStatus {
  bool statusExpanderPresent = false;
  bool controlExpanderPresent = false;
  bool nfcResponding = false;
  bool subGhzResponding = false;
  bool nfcResetReleased = false;
  bool chargerUsb100Mode = true;
  bool chargerDisabled = false;
  bool aux5Enabled = false;
  bool gnssPowerEnabled = false;
  bool boost5Enabled = false;
  bool sdDetected = false;
  bool chargerActive = false;
  bool externalPowerGood = false;
  bool aux5FaultActive = false;
  bool fuelGaugeAlertActive = false;
  bool bmiInt1 = false;
  bool bmiInt2 = false;
  bool bmpInt = false;
  bool userButtonAPressed = false;
  bool userButtonBPressed = false;
  uint8_t cc1101PartNumber = 0xFF;
  uint8_t cc1101Version = 0xFF;
  uint8_t statusInputs0 = 0xFF;
  uint8_t expansionInputs = 0xFF;
  uint8_t controlInputs = 0xFF;
};

class HardwareManager {
 public:
  void begin();
  void poll();

  bool setGnssPower(bool enabled);
  bool setBoost5(bool enabled);
  bool sendIrNec(uint8_t address, uint8_t command, uint8_t repeats = 0);
  bool readDirectGpio(uint8_t gpio, bool &level) const;

  const HardwareStatus &status() const { return status_; }
  String statusJson() const;

 private:
  static void setSafeOutput(uint8_t pin, uint8_t level);
  bool probeI2cAddress(uint8_t address);
  bool configureStatusExpander();
  bool configureControlExpander();
  bool writeI2cRegister(uint8_t address, uint8_t reg, uint8_t value);
  bool readI2cRegister(uint8_t address, uint8_t reg, uint8_t &value);
  bool setControlOutput(uint8_t bit, bool high);
  uint8_t readCc1101StatusRegister(uint8_t address);
  void probeSubGhz();
  void updateStatusExpanderInputs();
  void updateControlExpanderInputs();
  static void sendIrMark(uint32_t durationUs);
  static void sendIrSpace(uint32_t durationUs);
  static void sendIrByteLsb(uint8_t value);

  HardwareStatus status_;
  uint8_t controlOutputs_ = 0;
  uint32_t lastPollMs_ = 0;
  uint32_t lastIrTxMs_ = 0;
};

}  // namespace pocketlab
