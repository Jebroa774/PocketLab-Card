#pragma once

#include <Arduino.h>
#include <FS.h>
#include <SD.h>

namespace pocketlab {

class StorageManager {
 public:
  bool begin();
  bool remount();
  bool available() const { return mounted_; }
  uint64_t totalBytes() const;
  uint64_t usedBytes() const;

  bool normalizePath(const String &requested, String &normalized,
                     bool allowRoot = true) const;
  String listJson(const String &requestedPath) const;
  String statusJson() const;

  File openRead(const String &normalizedPath) const;
  File openAppend(const String &normalizedPath) const;
  bool ensureDirectory(const String &normalizedPath) const;
  bool removePath(const String &normalizedPath) const;

  bool beginUpload(const String &normalizedPath);
  bool writeUpload(const uint8_t *data, size_t length);
  bool finishUpload(bool keepFile);
  bool uploadActive() const { return static_cast<bool>(uploadFile_); }

 private:
  bool mount();

  bool mounted_ = false;
  File uploadFile_;
  String uploadPath_;
};

}  // namespace pocketlab
