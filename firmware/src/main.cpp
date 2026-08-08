#include <Arduino.h>

#include "board_pins.h"

using namespace pocketlab;

namespace {

void setSafeOutput(uint8_t pin, uint8_t level) {
  digitalWrite(pin, level);
  pinMode(pin, OUTPUT);
}

}  // namespace

void setup() {
  Serial.begin(115200);

  // Keep radios and high-current outputs inactive during early bring-up.
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

  Serial.println("PocketLab Card V1 firmware scaffold");
  Serial.printf("Direct expansion GPIO count: %u\n",
                static_cast<unsigned>(sizeof(pins::DIRECT_EXPANSION)));
}

void loop() {
  delay(1000);
}
