#pragma once

#include <Arduino.h>

namespace pocketlab::json {

inline String escape(const String &value) {
  String result;
  result.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    switch (c) {
      case '"': result += F("\\\""); break;
      case '\\': result += F("\\\\"); break;
      case '\b': result += F("\\b"); break;
      case '\f': result += F("\\f"); break;
      case '\n': result += F("\\n"); break;
      case '\r': result += F("\\r"); break;
      case '\t': result += F("\\t"); break;
      default:
        if (static_cast<uint8_t>(c) < 0x20) {
          char encoded[7];
          snprintf(encoded, sizeof(encoded), "\\u%04x", static_cast<uint8_t>(c));
          result += encoded;
        } else {
          result += c;
        }
    }
  }
  return result;
}

inline const __FlashStringHelper *boolean(bool value) {
  return value ? F("true") : F("false");
}

inline String quote(const String &value) {
  return String('"') + escape(value) + '"';
}

}  // namespace pocketlab::json
