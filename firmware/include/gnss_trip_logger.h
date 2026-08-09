#pragma once

#include <Arduino.h>
#include <FS.h>

#include "storage_manager.h"

namespace pocketlab {

struct GnssFix {
  bool valid = false;
  double latitude = 0.0;
  double longitude = 0.0;
  float altitudeMeters = 0.0F;
  float speedKmh = 0.0F;
  float courseDegrees = 0.0F;
  float hdop = 99.9F;
  uint8_t satellites = 0;
  String utc;
  uint32_t receivedAtMs = 0;
};

class GnssTripLogger {
 public:
  explicit GnssTripLogger(StorageManager &storage);

  void begin();
  void poll();
  bool startTrip(String &error);
  void stopTrip();

  bool tripActive() const { return tripActive_; }
  bool hasFreshFix() const;
  const GnssFix &fix() const { return fix_; }
  String statusJson() const;

 private:
  bool consumeNmeaLine(char *line);
  bool parseRmc(char **fields, size_t count);
  bool parseGga(char **fields, size_t count);
  static bool verifyChecksum(const char *line);
  static bool parseCoordinate(const char *value, const char *hemisphere, double &result);
  static String makeUtc(const char *date, const char *time);
  static double distanceMeters(double lat1, double lon1, double lat2, double lon2);
  void maybeLogFix();

  StorageManager &storage_;
  HardwareSerial serial_;
  GnssFix fix_;
  char lineBuffer_[128] = {};
  size_t lineLength_ = 0;
  uint32_t validSentenceCount_ = 0;
  uint32_t checksumErrorCount_ = 0;

  File tripFile_;
  bool tripActive_ = false;
  String tripPath_;
  uint32_t tripStartedAtMs_ = 0;
  uint32_t lastLogAtMs_ = 0;
  uint32_t lastFlushAtMs_ = 0;
  uint32_t loggedPointCount_ = 0;
  double tripDistanceMeters_ = 0.0;
  bool havePreviousPoint_ = false;
  double previousLatitude_ = 0.0;
  double previousLongitude_ = 0.0;
};

}  // namespace pocketlab
