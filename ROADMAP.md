# Roadmap

## 1. Identification and Communication

- [ ] Record photos or information from the device label, variant, and firmware, if available.
- [x] Identify QLabel by Play Store URL, package name, and version.
- [x] Record Linux distribution, kernel, and Bluetooth adapter used in tests.
- [x] Verify discovery and pairing on Linux.
- [x] Identify the transport used in the tested path: Classic Bluetooth/RFCOMM.
- [x] Record available services, UUIDs, characteristics, and properties.

## 2. Protocol

- [ ] Capture a known print session with QLabel.
- [x] Correlate transmitted data with label content and dimensions.
- [x] Identify configuration, raster encoding, and termination for the proof of concept.
- [x] Determine fragmentation, send limits, acknowledgments, and timing.
- [x] Document the raster path with examples and confidence levels for conclusions.

## 3. Linux Proof of Concept

- [x] Implement connection and transmission based on the observed protocol.
- [x] Print a test label on the physical E210.
- [x] Document the complete procedure and results.
- [x] Handle disconnection, unavailability, and observed errors.

## 4. Daily Usage

- [x] Implement PNG conversion to the format accepted by the printer.
- [x] Provide a command-line interface.
- [x] Document installation, permissions, and troubleshooting.
- [x] Add tests for protocol and image processing components.
- [ ] Evaluate CUPS integration after direct printing stabilizes.
