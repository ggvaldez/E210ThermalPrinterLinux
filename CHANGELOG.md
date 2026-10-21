# Changelog

## v0.1.0 — 2026-10-21 (pre-release)

Initial experimental release for the E210 on Linux, using the protocol
recovered from QLabel. No Android application or Windows driver is needed.

- Print PNG images over Bluetooth Classic/BlueZ or USB/libusb, with automatic
  device discovery and explicit device selection.
- Convert images to the validated 384-dot width (48 mm), with dithering or
  threshold conversion, density selection, previews, copies and media modes.
- Integrate with CUPS through a raster filter, PPD and Bluetooth/USB backend.
- Decode compressed CUPS/PWG raster through native libcups.
- Fit artwork within both label dimensions, trim continuous-paper padding,
  preserve document scale when selected, and align narrow output to the right.
- Supply standard PPD media names, exact physical dimensions and fixed
  203 dpi resolution, with warning-free PPD validation.
- Reduce Bluetooth discovery/connection delays for known or detected printers.
- Preserve the existing CUPS connection during installation updates, with
  explicit `--usb` and `--bluetooth` switches.

Validation: 63 automated tests passed. Bluetooth printing and the integrated
USB PNG command were physically confirmed on the tested E210. End-to-end
printing from an installed CUPS queue over USB still needs physical
confirmation. Black-mark media, other firmware variants and other printer
models are not validated. TSPL is not supported by this implementation.

PPD upgrade: saved print settings using `Continuous50mm`, `Label…` or
`CableWrap` must select the new standard media names after reinstalling.
Use `PageSize=50x50mm` with `MediaType=Gap` for 50 by 50 mm die-cut labels;
page size and roll type are separate settings.
