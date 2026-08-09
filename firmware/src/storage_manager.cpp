#include "storage_manager.h"

#include "board_pins.h"
#include "firmware_config.h"
#include "json_util.h"

namespace pocketlab {

bool StorageManager::begin() {
  return mount();
}

bool StorageManager::mount() {
  digitalWrite(pins::SUBGHZ_CS_N, HIGH);
  digitalWrite(pins::SD_CS_N, HIGH);
  mounted_ = SD.begin(pins::SD_CS_N, SPI, config::SD_FREQUENCY_HZ);
  if (mounted_) {
    ensureDirectory(F("/trips"));
    ensureDirectory(F("/uploads"));
  }
  return mounted_;
}

bool StorageManager::remount() {
  if (uploadFile_) {
    uploadFile_.close();
    uploadPath_ = String();
  }
  SD.end();
  mounted_ = false;
  delay(10);
  return mount();
}

uint64_t StorageManager::totalBytes() const {
  return mounted_ ? SD.totalBytes() : 0;
}

uint64_t StorageManager::usedBytes() const {
  return mounted_ ? SD.usedBytes() : 0;
}

bool StorageManager::normalizePath(const String &requested, String &normalized,
                                   bool allowRoot) const {
  String path = requested;
  path.trim();
  path.replace('\\', '/');
  if (path.isEmpty()) path = F("/");
  if (!path.startsWith(F("/"))) path = '/' + path;

  if (path.length() > config::MAX_FILE_PATH_LENGTH || path.indexOf(F("..")) >= 0 ||
      path.indexOf(F("//")) >= 0) {
    return false;
  }
  for (size_t i = 0; i < path.length(); ++i) {
    const uint8_t c = static_cast<uint8_t>(path[i]);
    if (c < 0x20 || c == 0x7F || c == ':' || c == '*' || c == '"') return false;
  }
  while (path.length() > 1 && path.endsWith(F("/"))) path.remove(path.length() - 1);
  if (!allowRoot && path == F("/")) return false;
  normalized = path;
  return true;
}

String StorageManager::statusJson() const {
  String result;
  result.reserve(128);
  result += F("{\"mounted\":");
  result += json::boolean(mounted_);
  result += F(",\"totalBytes\":");
  result += String(static_cast<unsigned long long>(totalBytes()));
  result += F(",\"usedBytes\":");
  result += String(static_cast<unsigned long long>(usedBytes()));
  result += '}';
  return result;
}

String StorageManager::listJson(const String &requestedPath) const {
  String path;
  if (!mounted_) return F("{\"ok\":false,\"error\":\"sd_not_mounted\"}");
  if (!normalizePath(requestedPath, path)) {
    return F("{\"ok\":false,\"error\":\"invalid_path\"}");
  }

  File directory = SD.open(path);
  if (!directory || !directory.isDirectory()) {
    if (directory) directory.close();
    return F("{\"ok\":false,\"error\":\"directory_not_found\"}");
  }

  String result;
  result.reserve(1024);
  result += F("{\"ok\":true,\"path\":\"");
  result += json::escape(path);
  result += F("\",\"entries\":[");

  size_t count = 0;
  bool truncated = false;
  while (true) {
    File entry = directory.openNextFile();
    if (!entry) break;
    if (count >= config::MAX_DIRECTORY_ENTRIES) {
      truncated = true;
      entry.close();
      break;
    }

    if (count > 0) result += ',';
    String name = entry.name();
    if (!name.startsWith(F("/"))) {
      name = path == F("/") ? '/' + name : path + '/' + name;
    }
    result += F("{\"name\":\"");
    result += json::escape(name);
    result += F("\",\"directory\":");
    result += json::boolean(entry.isDirectory());
    result += F(",\"size\":");
    result += String(static_cast<unsigned long>(entry.size()));
    result += '}';
    ++count;
    entry.close();
  }
  directory.close();

  result += F("],\"truncated\":");
  result += json::boolean(truncated);
  result += '}';
  return result;
}

File StorageManager::openRead(const String &normalizedPath) const {
  if (!mounted_) return File();
  return SD.open(normalizedPath, FILE_READ);
}

File StorageManager::openAppend(const String &normalizedPath) const {
  if (!mounted_) return File();
  return SD.open(normalizedPath, FILE_APPEND);
}

bool StorageManager::ensureDirectory(const String &normalizedPath) const {
  if (!mounted_) return false;
  File existing = SD.open(normalizedPath);
  if (existing) {
    const bool isDirectory = existing.isDirectory();
    existing.close();
    return isDirectory;
  }
  return SD.mkdir(normalizedPath);
}

bool StorageManager::removePath(const String &normalizedPath) const {
  if (!mounted_ || normalizedPath == F("/")) return false;
  File item = SD.open(normalizedPath);
  if (!item) return false;
  const bool isDirectory = item.isDirectory();
  item.close();
  return isDirectory ? SD.rmdir(normalizedPath) : SD.remove(normalizedPath);
}

bool StorageManager::beginUpload(const String &normalizedPath) {
  if (!mounted_ || uploadFile_ || normalizedPath == F("/")) return false;
  uploadFile_ = SD.open(normalizedPath, FILE_WRITE);
  if (!uploadFile_) return false;
  uploadPath_ = normalizedPath;
  return true;
}

bool StorageManager::writeUpload(const uint8_t *data, size_t length) {
  if (!uploadFile_ || data == nullptr) return false;
  return uploadFile_.write(data, length) == length;
}

bool StorageManager::finishUpload(bool keepFile) {
  if (!uploadFile_) return false;
  uploadFile_.flush();
  uploadFile_.close();
  const String completedPath = uploadPath_;
  uploadPath_ = String();
  if (!keepFile) SD.remove(completedPath);
  return keepFile;
}

}  // namespace pocketlab
