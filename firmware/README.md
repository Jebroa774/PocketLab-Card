# Firmware baseline

The target is Arduino-ESP32 3.x under PlatformIO, with native USB enabled.
This keeps PN532, CC1101, microSD and IR library options broad while retaining
reproducible command-line builds.

Planned services:

- Local access point and responsive web application
- WebSocket event/status stream
- NFC read/write tools
- Sub-GHz receive/transmit tools for authorized use
- IR learning, protocol decoding and transmission
- GNSS live status and 5 Hz trip logger
- GPX/CSV trip export and microSD file management
- Battery, charging, sensor and diagnostic status
- GPIO laboratory for direct and expanded header pins

`include/board_pins.h` mirrors `docs/pinout.md` and is the firmware source of
truth once the schematic has passed ERC.
