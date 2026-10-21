# E210 Thermal Printer Linux

Python application to print PNG images on the Bluetooth **E210 thermal printer from Linux**, without relying on a smartphone or the QLabel app during printing.

Printing has been physically validated on an E210 with **50 mm continuous paper**, using CachyOS and BlueZ. Both a geometric test pattern and PNG images sent from the command line printed successfully.

## Requirements

- Linux with active BlueZ service and a Bluetooth adapter supporting Classic Bluetooth/RFCOMM.
- Python 3, Pillow, dbus-python, and PyGObject.
- E210 turned on, loaded with 50 mm continuous paper, with no active connection to a smartphone.

Communication uses modern BlueZ D-Bus APIs. Installing `sdptool` or deprecated Bluetooth utilities is not required.

## Installation

Clone the repository and enter the directory:

```bash
git clone https://github.com/ggvaldez/E210ThermalPrinterLinux.git
cd E210ThermalPrinterLinux
```

On CachyOS or Arch Linux, install native dependencies:

```bash
sudo pacman -S --needed bluez bluez-utils python python-pillow python-dbus python-gobject
sudo systemctl enable --now bluetooth.service
```

On other distributions, install the equivalent packages using your system package manager. The implementation does not depend specifically on CachyOS, though other distributions have not yet been tested in this project. The examples below use `python`; if your distribution provides the interpreter as `python3`, adjust the command accordingly.

## Automatic Discovery and Registered Devices

Without `--address`, the script first checks whether an E210 is already registered in BlueZ. If found, it uses that printer immediately without delay. If not already registered, it searches for an E210 for 10 seconds on the selected adapter:

```bash
python tools/print_png.py image.png
```

Turn on the printer and disconnect it from your smartphone before running. The search uses Classic Bluetooth via BlueZ. If an E210 is found or already registered, it displays the address and prints; if none is found, it reports the issue. If more than one printer is found, it lists their addresses and asks you to specify one with `--address`. `--adapter hci1` allows choosing a different adapter. `--dry-run` skips discovery and Bluetooth connection.

### Discovering the Address Manually

Turn on the E210 and disconnect QLabel or turn off Bluetooth on your smartphone. In the terminal, run:

```bash
bluetoothctl
```

Inside `bluetoothctl`:

```text
power on
scan on
```

Wait for a line similar to this to appear and note your printer's address:

```text
Device AA:BB:CC:DD:EE:FF E210
```

Stop scanning and exit:

```text
scan off
quit
```

On the tested unit, connection worked without manual pairing. The program discovers the serial channel via service UUID; configuring an RFCOMM channel manually is not necessary.

## Printing a PNG

Run from the project root, replacing the image path and Bluetooth address:

```bash
python tools/print_png.py image.png --address AA:BB:CC:DD:EE:FF
```

Each run prints **one copy** by default. Paths containing spaces must be enclosed in quotes.

### Gap Labels and Multiple Copies

To print three copies on 50 × 50 mm labels with gaps:

```bash
python tools/print_png.py image.png --address AA:BB:CC:DD:EE:FF --media gap --label-height 50 --copies 3
```

`--label-height` is the physical label height in millimeters, excluding the gap; media width remains 50 mm. The raster preserves its aspect ratio and must fit within the specified height. `--media` accepts `continuous` (default), `gap`, and `black-mark`. Gap and black-mark labels require an explicit height. The black-mark option was identified in Java, but has not yet been physically tested. Each copy sends a complete page with its own feed command; it does not rely on an internal firmware copy counter.

Images are resized to **384 pixels wide**, preserving aspect ratio. This is the largest raster width validated so far, equivalent to **48 mm at 8 dots/mm**, approximately 203 dpi. The absolute physical limit of the printer is not yet established.

For maximum sharpness and pixel-level control, prepare the PNG already at 384 pixels wide. A 384 × 384 pixel file produces an approximately 48 × 48 mm raster. PNG DPI metadata does not affect dimensions; height is calculated from the aspect ratio. Physical margins and feed distance may differ from raster size.

Transparency is composited over white. Grayscale images are converted to black and white using Floyd–Steinberg dithering. Transmission occurs **without artificial pauses**, following Bluetooth socket readiness. Each copy ends with **`1B 69` followed by `1B 4A 00`**, ensuring printing completes before feeding. This ordering applies to all modes; media type is configured separately.

### Preview Without Printing

```bash
python tools/print_png.py image.png --dry-run --preview preview.png
```

This prepares the image without connecting to the printer. The preview command will not overwrite existing files.

### Settings and Adjustments

To use a fixed black-and-white threshold instead of dithering:

```bash
python tools/print_png.py image.png --address AA:BB:CC:DD:EE:FF --threshold 128
```

To adjust thermal density or select another adapter:

```bash
python tools/print_png.py image.png --address AA:BB:CC:DD:EE:FF --density 6 --adapter hci0
```

`--density` accepts values from 0 to 16 (default: 6). `--threshold` accepts 0 to 255.

To test slower transmission, use `--pause-ms 50`. The default is **0 ms**. The pause applies between commands and rows; the connection timeout scales to the estimated job duration. Changing pause does not alter pixels or configured thermal density.

Unpaused transmission with corrected termination command order was physically validated with **20 consecutive staircases**, complete and joined, totaling 87,160 bytes. Mechanical pauses occurred during execution with no observed loss of content. This does not define the internal buffer capacity.

For diagnostics, `--finish-delay-ms 2000` inserts 2 seconds before the final command pair of each copy. The default is zero: extra delays were not needed in the 20-staircase test. Extensive validation of the corrected order was performed on continuous paper; feed behavior on sensor-equipped labels should still be reconfirmed.

View all options with:

```bash
python tools/print_png.py --help
```

## Troubleshooting

- **Error importing PIL, dbus, or gi:** check dependencies and make sure you are using the system Python where native packages were installed.
- **Cannot connect:** check power, Bluetooth address, and `bluetooth.service`; disconnect printer from other devices. Your user account must have access to BlueZ over the system D-Bus.
- **Incomplete print or feeding before finishing:** update code. The initial sequence fed before completion; physical testing validated reversing the final two commands.
- **Pauses during a long job:** the 20-staircase test showed pauses but finished every image. The program handles partial socket writes and does not automatically retry failed jobs. If a print fails, check physical output before re-sending to avoid duplicate copies.

To query status without printing:

```bash
python tools/probe_bluez.py AA:BB:CC:DD:EE:FF --query status --timeout 20
```

"Send completed" confirms socket transmission, not physical paper exit. In our tests, successful printing was confirmed through physical user observation.

## Other Printers and Platforms

**Need support for another printer or platform, such as Windows or macOS? [Open an issue](https://github.com/ggvaldez/E210ThermalPrinterLinux/issues).**

Please provide the exact model, operating system and version, and any working mobile app. This information helps assess compatibility. New models and platforms require dedicated implementation and testing.

PNG conversion and command encoding are written in Python and can be ported to other platforms. The current Bluetooth connection relies on BlueZ on Linux. We do not assume that other printers use the same protocol as the E210.

## Development and Documentation

To run automated tests:

```bash
python -m unittest discover -s tests -v
```

- [Java analysis and command format](docs/JAVA_ANALYSIS.md)
- [BlueZ connection and physical test results](docs/BLUETOOTH_LINUX.md)
- [Investigation roadmap](docs/INVESTIGATION.md)
- [Roadmap](ROADMAP.md)

QLabel 29.0.22 served as reference to investigate the protocol. The Python application does not require the APK, Android, or extracted native libraries to function.

APKs, decompilations, logs, and local captures are kept out of version control. Review device identifiers before posting captures or logs in an issue.
