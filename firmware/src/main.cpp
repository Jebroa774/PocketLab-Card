#include <Arduino.h>

#include "firmware_config.h"
#include "hardware_manager.h"
#include "storage_manager.h"
#include "web_portal.h"

namespace {

pocketlab::HardwareManager hardware;
pocketlab::StorageManager storage;
pocketlab::WebPortal web(hardware, storage);

}  // namespace

void setup() {
  Serial.begin(115200);
  const uint32_t serialWaitStarted = millis();
  while (!Serial && millis() - serialWaitStarted < 1500) delay(10);

  Serial.println();
  Serial.printf("%s firmware %s (HW rev %d)\n", pocketlab::config::FIRMWARE_NAME,
                pocketlab::config::FIRMWARE_VERSION, POCKETLAB_CARD_HW_REV);
  Serial.println(F("Initializing outputs in safe state..."));

  hardware.begin();
  const bool sdMounted = storage.begin();
  const bool webStarted = web.begin();

  Serial.printf("microSD: %s\n", sdMounted ? "mounted" : "not detected");
  Serial.printf("Web portal: %s\n", webStarted ? "ready" : "failed");
  if (webStarted) {
    Serial.printf("Wi-Fi SSID: %s\n", web.ssid().c_str());
    Serial.printf("Wi-Fi password: %s\n", web.password().c_str());
    Serial.println(F("Open http://192.168.4.1/ after connecting."));
  }
  Serial.printf("TX policy: Sub-GHz=%s IR=%s GPIO-output=%s\n",
                pocketlab::config::SUBGHZ_TX_COMPILED ? "compiled" : "locked",
                pocketlab::config::IR_TX_COMPILED ? "compiled" : "locked",
                pocketlab::config::GPIO_OUTPUT_COMPILED ? "compiled" : "locked");
}

void loop() {
  hardware.poll();
  web.poll();
  delay(1);
}
