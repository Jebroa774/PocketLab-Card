#include "gnss_trip_logger.h"

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <esp_system.h>

#include "board_pins.h"
#include "firmware_config.h"
#include "json_util.h"

namespace pocketlab {
namespace {

uint8_t hexNibble(char c) {
  if (c >= '0' && c <= '9') return static_cast<uint8_t>(c - '0');
  if (c >= 'A' && c <= 'F') return static_cast<uint8_t>(c - 'A' + 10);
  if (c >= 'a' && c <= 'f') return static_cast<uint8_t>(c - 'a' + 10);
  return 0xFF;
}

bool sentenceTypeIs(const char *field, const char *suffix) {
  if (field == nullptr || suffix == nullptr) return false;
  const size_t fieldLength = strlen(field);
  const size_t suffixLength = strlen(suffix);
  return fieldLength >= suffixLength &&
         strcmp(field + fieldLength - suffixLength, suffix) == 0;
}

}  // namespace

GnssTripLogger::GnssTripLogger(StorageManager &storage)
    : storage_(storage), serial_(1) {}

void GnssTripLogger::begin() {
  serial_.begin(config::GNSS_BAUD, SERIAL_8N1, pins::GNSS_RX_FROM_MODULE,
                pins::GNSS_TX_TO_MODULE);
}

void GnssTripLogger::poll() {
  while (serial_.available() > 0) {
    const char c = static_cast<char>(serial_.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (lineLength_ > 0) {
        lineBuffer_[lineLength_] = '\0';
        consumeNmeaLine(lineBuffer_);
        lineLength_ = 0;
      }
      continue;
    }

    if (lineLength_ < config::MAX_NMEA_LINE_LENGTH) {
      lineBuffer_[lineLength_++] = c;
    } else {
      // Drop an overlong sentence as a unit.
      lineLength_ = 0;
    }
  }

  if (tripActive_ && millis() - lastFlushAtMs_ >= config::TRIP_FLUSH_INTERVAL_MS) {
    tripFile_.flush();
    lastFlushAtMs_ = millis();
  }
}

bool GnssTripLogger::verifyChecksum(const char *line) {
  if (line == nullptr || line[0] != '$') return false;
  const char *star = strchr(line, '*');
  if (star == nullptr || star[1] == '\0' || star[2] == '\0') return false;

  uint8_t calculated = 0;
  for (const char *cursor = line + 1; cursor < star; ++cursor) {
    calculated ^= static_cast<uint8_t>(*cursor);
  }
  const uint8_t high = hexNibble(star[1]);
  const uint8_t low = hexNibble(star[2]);
  if (high == 0xFF || low == 0xFF) return false;
  return calculated == static_cast<uint8_t>((high << 4) | low);
}

bool GnssTripLogger::consumeNmeaLine(char *line) {
  if (!verifyChecksum(line)) {
    ++checksumErrorCount_;
    return false;
  }
  ++validSentenceCount_;

  char *star = strchr(line, '*');
  *star = '\0';
  char *payload = line + 1;
  char *fields[24] = {};
  size_t count = 0;
  fields[count++] = payload;
  for (char *cursor = payload; *cursor != '\0' && count < 24; ++cursor) {
    if (*cursor == ',') {
      *cursor = '\0';
      fields[count++] = cursor + 1;
    }
  }

  if (sentenceTypeIs(fields[0], "RMC")) return parseRmc(fields, count);
  if (sentenceTypeIs(fields[0], "GGA")) return parseGga(fields, count);
  return true;
}

bool GnssTripLogger::parseCoordinate(const char *value, const char *hemisphere,
                                     double &result) {
  if (value == nullptr || hemisphere == nullptr || *value == '\0' || *hemisphere == '\0') {
    return false;
  }
  char *end = nullptr;
  const double degreesMinutes = strtod(value, &end);
  if (end == value || !std::isfinite(degreesMinutes)) return false;
  const double degrees = floor(degreesMinutes / 100.0);
  const double minutes = degreesMinutes - degrees * 100.0;
  if (minutes < 0.0 || minutes >= 60.0) return false;
  result = degrees + minutes / 60.0;
  if (*hemisphere == 'S' || *hemisphere == 'W') result = -result;
  return *hemisphere == 'N' || *hemisphere == 'S' || *hemisphere == 'E' ||
         *hemisphere == 'W';
}

String GnssTripLogger::makeUtc(const char *date, const char *time) {
  if (date == nullptr || time == nullptr || strlen(date) < 6 || strlen(time) < 6) {
    return String();
  }
  const int day = (date[0] - '0') * 10 + (date[1] - '0');
  const int month = (date[2] - '0') * 10 + (date[3] - '0');
  const int shortYear = (date[4] - '0') * 10 + (date[5] - '0');
  const int year = shortYear >= 80 ? 1900 + shortYear : 2000 + shortYear;
  const int hour = (time[0] - '0') * 10 + (time[1] - '0');
  const int minute = (time[2] - '0') * 10 + (time[3] - '0');
  const int second = (time[4] - '0') * 10 + (time[5] - '0');
  if (day < 1 || day > 31 || month < 1 || month > 12 || hour > 23 || minute > 59 ||
      second > 60) {
    return String();
  }
  char utc[25];
  snprintf(utc, sizeof(utc), "%04d-%02d-%02dT%02d:%02d:%02dZ", year, month, day,
           hour, minute, second);
  return String(utc);
}

bool GnssTripLogger::parseRmc(char **fields, size_t count) {
  if (count < 10) return false;
  double latitude = 0.0;
  double longitude = 0.0;
  const bool active = fields[2][0] == 'A';
  const bool coordinatesValid = parseCoordinate(fields[3], fields[4], latitude) &&
                                parseCoordinate(fields[5], fields[6], longitude);

  fix_.valid = active && coordinatesValid;
  fix_.receivedAtMs = millis();
  if (!fix_.valid) return true;

  fix_.latitude = latitude;
  fix_.longitude = longitude;
  fix_.speedKmh = static_cast<float>(atof(fields[7]) * 1.852);
  fix_.courseDegrees = static_cast<float>(atof(fields[8]));
  fix_.utc = makeUtc(fields[9], fields[1]);
  maybeLogFix();
  return true;
}

bool GnssTripLogger::parseGga(char **fields, size_t count) {
  if (count < 10) return false;
  const int quality = atoi(fields[6]);
  fix_.satellites = static_cast<uint8_t>(constrain(atoi(fields[7]), 0, 255));
  fix_.hdop = static_cast<float>(atof(fields[8]));
  fix_.altitudeMeters = static_cast<float>(atof(fields[9]));
  if (quality == 0 && millis() - fix_.receivedAtMs > 1000) fix_.valid = false;
  return true;
}

bool GnssTripLogger::hasFreshFix() const {
  return fix_.valid && millis() - fix_.receivedAtMs <= config::GNSS_FIX_TIMEOUT_MS;
}

bool GnssTripLogger::startTrip(String &error) {
  error = String();
  if (tripActive_) return true;
  if (!storage_.available()) {
    error = F("sd_not_mounted");
    return false;
  }
  if (!storage_.ensureDirectory(F("/trips"))) {
    error = F("trip_directory_unavailable");
    return false;
  }

  char filename[64];
  if (fix_.utc.length() >= 19) {
    snprintf(filename, sizeof(filename), "/trips/trip_%.4s%.2s%.2s_%.2s%.2s%.2s_%04lX.csv",
             fix_.utc.c_str(), fix_.utc.c_str() + 5, fix_.utc.c_str() + 8,
             fix_.utc.c_str() + 11, fix_.utc.c_str() + 14, fix_.utc.c_str() + 17,
             static_cast<unsigned long>(esp_random() & 0xFFFF));
  } else {
    snprintf(filename, sizeof(filename), "/trips/trip_boot_%010lu_%04lX.csv",
             static_cast<unsigned long>(millis()),
             static_cast<unsigned long>(esp_random() & 0xFFFF));
  }

  tripPath_ = filename;
  tripFile_ = storage_.openAppend(tripPath_);
  if (!tripFile_) {
    error = F("trip_file_open_failed");
    tripPath_ = String();
    return false;
  }
  tripFile_.println(F("utc,latitude,longitude,speed_kmh,course_deg,altitude_m,satellites,hdop"));
  tripFile_.flush();

  tripActive_ = true;
  tripStartedAtMs_ = millis();
  lastLogAtMs_ = 0;
  lastFlushAtMs_ = tripStartedAtMs_;
  loggedPointCount_ = 0;
  tripDistanceMeters_ = 0.0;
  havePreviousPoint_ = false;
  return true;
}

void GnssTripLogger::stopTrip() {
  if (tripFile_) {
    tripFile_.flush();
    tripFile_.close();
  }
  tripActive_ = false;
}

double GnssTripLogger::distanceMeters(double lat1, double lon1, double lat2,
                                      double lon2) {
  constexpr double earthRadiusMeters = 6371000.0;
  constexpr double radiansPerDegree = PI / 180.0;
  const double dLat = (lat2 - lat1) * radiansPerDegree;
  const double dLon = (lon2 - lon1) * radiansPerDegree;
  const double rLat1 = lat1 * radiansPerDegree;
  const double rLat2 = lat2 * radiansPerDegree;
  const double rawA = sin(dLat / 2.0) * sin(dLat / 2.0) +
                      cos(rLat1) * cos(rLat2) * sin(dLon / 2.0) * sin(dLon / 2.0);
  const double a = fmax(0.0, fmin(1.0, rawA));
  return earthRadiusMeters * 2.0 * atan2(sqrt(a), sqrt(1.0 - a));
}

void GnssTripLogger::maybeLogFix() {
  if (!tripActive_ || !tripFile_ || !hasFreshFix()) return;
  const uint32_t now = millis();
  if (lastLogAtMs_ != 0 && now - lastLogAtMs_ < config::TRIP_LOG_INTERVAL_MS) return;

  if (havePreviousPoint_) {
    const double segment = distanceMeters(previousLatitude_, previousLongitude_, fix_.latitude,
                                          fix_.longitude);
    // Reject impossible one-second jumps while retaining normal vehicle speeds.
    if (segment >= 0.0 && segment < 500.0) tripDistanceMeters_ += segment;
  }
  previousLatitude_ = fix_.latitude;
  previousLongitude_ = fix_.longitude;
  havePreviousPoint_ = true;

  tripFile_.print(fix_.utc);
  tripFile_.print(',');
  tripFile_.print(fix_.latitude, 7);
  tripFile_.print(',');
  tripFile_.print(fix_.longitude, 7);
  tripFile_.print(',');
  tripFile_.print(fix_.speedKmh, 2);
  tripFile_.print(',');
  tripFile_.print(fix_.courseDegrees, 1);
  tripFile_.print(',');
  tripFile_.print(fix_.altitudeMeters, 1);
  tripFile_.print(',');
  tripFile_.print(fix_.satellites);
  tripFile_.print(',');
  tripFile_.println(fix_.hdop, 1);

  lastLogAtMs_ = now;
  ++loggedPointCount_;
  if (loggedPointCount_ % 10 == 0) {
    tripFile_.flush();
    lastFlushAtMs_ = now;
  }
}

String GnssTripLogger::statusJson() const {
  String result;
  result.reserve(512);
  result += F("{\"freshFix\":");
  result += json::boolean(hasFreshFix());
  result += F(",\"valid\":");
  result += json::boolean(fix_.valid);
  result += F(",\"latitude\":");
  result += String(fix_.latitude, 7);
  result += F(",\"longitude\":");
  result += String(fix_.longitude, 7);
  result += F(",\"speedKmh\":");
  result += String(fix_.speedKmh, 2);
  result += F(",\"courseDegrees\":");
  result += String(fix_.courseDegrees, 1);
  result += F(",\"altitudeMeters\":");
  result += String(fix_.altitudeMeters, 1);
  result += F(",\"satellites\":");
  result += static_cast<unsigned>(fix_.satellites);
  result += F(",\"hdop\":");
  result += String(fix_.hdop, 1);
  result += F(",\"utc\":\"");
  result += json::escape(fix_.utc);
  result += F("\",\"validSentences\":");
  result += validSentenceCount_;
  result += F(",\"checksumErrors\":");
  result += checksumErrorCount_;
  result += F(",\"trip\":{\"active\":");
  result += json::boolean(tripActive_);
  result += F(",\"path\":\"");
  result += json::escape(tripPath_);
  result += F("\",\"points\":");
  result += loggedPointCount_;
  result += F(",\"distanceMeters\":");
  result += String(tripDistanceMeters_, 1);
  result += F(",\"durationMs\":");
  result += tripActive_ ? millis() - tripStartedAtMs_ : 0;
  result += F("}}");
  return result;
}

}  // namespace pocketlab
