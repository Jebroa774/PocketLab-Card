#pragma once

#include <Arduino.h>
#include <WebServer.h>
#include <WebSocketsServer.h>

#include "hardware_manager.h"
#include "storage_manager.h"

namespace pocketlab {

class WebPortal {
 public:
  WebPortal(HardwareManager &hardware, StorageManager &storage);

  bool begin();
  void poll();
  const String &ssid() const { return ssid_; }
  const String &password() const { return password_; }

 private:
  void configureRoutes();
  void sendJson(int code, const String &payload);
  void sendError(int code, const __FlashStringHelper *error);
  bool authorizeMutation();
  String buildStatusJson() const;
  String buildConfigJson() const;
  String gpioStatusJson() const;
  String contentType(const String &path) const;

  void handleFileList();
  void handleFileDownload();
  void handleFileDelete();
  void handleUploadChunk();
  void handleUploadComplete();
  void handleLfPower();
  void handleLfDiagnose();
  void handlePairingArm();
  void handleSdRemount();
  void handleIrTransmit();
  void handleLockedTransmit(const __FlashStringHelper *capability);

  HardwareManager &hardware_;
  StorageManager &storage_;
  WebServer server_;
  WebSocketsServer webSocket_;
  String ssid_;
  String password_;
  String sessionToken_;
  uint32_t lastBroadcastMs_ = 0;
  bool uploadAuthorized_ = false;
  bool uploadSucceeded_ = false;
  String uploadError_;
};

}  // namespace pocketlab
