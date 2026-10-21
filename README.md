# E210 Thermal Printer Linux

Python application to print PNG images on the **E210 thermal printer from Linux over Bluetooth or USB**, without relying on a smartphone or the QLabel app during printing.

Printing has been physically validated on an E210 with **50 mm continuous paper**, using CachyOS and BlueZ. Both a geometric test pattern and PNG images sent from the command line printed successfully. The same QLabel byte stream has also been physically validated over USB on the YICHIP `08c5:4001` interface.

## Requirements

- Python 3 and Pillow on Linux.
- USB: the system `libusb` library and a data-capable USB cable. No BlueZ, PyUSB or RFCOMM is required for USB printing.
- Bluetooth: active BlueZ service, a Classic Bluetooth/RFCOMM adapter, dbus-python and PyGObject.
- E210 turned on and loaded with paper; disconnect smartphone applications before printing over Bluetooth.

Communication uses modern BlueZ D-Bus APIs. Installing `sdptool` or deprecated Bluetooth utilities is not required.

## Installation

Clone the repository and enter the directory:

```bash
git clone https://github.com/ggvaldez/E210ThermalPrinterLinux.git
cd E210ThermalPrinterLinux
```

On CachyOS or Arch Linux, install native dependencies:

```bash
sudo pacman -S --needed libusb bluez bluez-utils python python-pillow python-dbus python-gobject
sudo systemctl enable --now bluetooth.service
```

On other distributions, install the equivalent packages using your system package manager. The implementation does not depend specifically on CachyOS, though other distributions have not yet been tested in this project. The examples below use `python`; if your distribution provides the interpreter as `python3`, adjust the command accordingly.

## Automatic Discovery and Registered Devices

Without `--address`, the script first checks whether an E210 is already registered in BlueZ. If found, it uses that printer immediately without delay. If not already registered, it searches for an E210 for 10 seconds on the selected adapter:

```bash
python tools/print_png.py image.png
```

Turn on the printer and disconnect it from your smartphone before running. The search uses Classic Bluetooth via BlueZ. If an E210 is found or already registered, it displays the address and prints; if none is found, it reports the issue. If more than one printer is found, it lists their addresses and asks you to specify one with `--address`. `--adapter hci1` allows choosing a different adapter. `--dry-run` skips discovery and connections for either transport.

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

### Printing over USB

Connect the printer with a USB data cable and run:

```bash
python tools/print_png.py image.png --transport usb
```

The program automatically selects the only connected device with VID/PID
`08c5:4001` (reported as `YICHIP YC3121 Printer demo` on the tested unit).
It opens interface 0 and writes to bulk OUT endpoint `0x01` using native
libusb. It does not require `/dev/usb/lp0` or an RFCOMM device.

When multiple printers are connected, select the bus/device shown by
`lsusb -d 08c5:4001`:

```bash
python tools/print_png.py image.png --transport usb --usb-device 001:028
```

The integrated command was physically validated with `teste.png`: automatic
USB selection, a 384 × 384 dot raster (48 × 48 mm), density 6, continuous
media, one copy and 11,713 transferred bytes. The user confirmed correct
output. CUPS USB uses this transport, but an end-to-end print from the
installed CUPS queue has not yet been confirmed.

Bus/device numbers can change after reconnecting; automatic selection avoids
storing those numbers. The generic YICHIP ID alone is not proof that another
printer model supports this protocol. `--address` and `--adapter` apply only
to Bluetooth, which remains the default transport.

Density, copies, media, previews and optional pacing work identically with
both connections. For example:

```bash
python tools/print_png.py image.png --transport usb --media gap --label-height 50 --copies 3
```

If USB access is denied, inspect `/dev/bus/usb/BUS/DEVICE` permissions. On the
tested system, the device is owned by group `lp`; local permissions/group
membership must permit read/write access. CUPS runs this project's backend
as root. libusb temporarily detaches a bound kernel printer driver when
necessary and reattaches it on release. Close competing print jobs/apps
before using the same interface. Failed jobs are not resent by the USB
sender; after resolving the error, submit the job again.

### Gap Labels and Multiple Copies

To print three copies on 50 × 50 mm labels with gaps:

```bash
python tools/print_png.py image.png --address AA:BB:CC:DD:EE:FF --media gap --label-height 50 --copies 3
```

`--label-height` is the physical label height in millimeters, excluding the gap; media width remains 50 mm. The raster preserves its aspect ratio and must fit within the specified height. `--media` accepts `continuous` (default), `gap`, and `black-mark`. Gap and black-mark labels require an explicit height. The black-mark option was identified in Java, but has not yet been physically tested. Each copy sends a complete page with its own feed command; it does not rely on an internal firmware copy counter.

Images are resized to **384 pixels wide**, preserving aspect ratio. This is the largest raster width validated so far, equivalent to **48 mm at 8 dots/mm**, approximately 203 dpi. The absolute physical limit of the printer is not yet established.

For maximum sharpness and pixel-level control, prepare the PNG already at 384 pixels wide. A 384 × 384 pixel file produces an approximately 48 × 48 mm raster. PNG DPI metadata does not affect dimensions; height is calculated from the aspect ratio. Physical margins and feed distance may differ from raster size.

Transparency is composited over white. Grayscale images are converted to black and white using Floyd–Steinberg dithering. Transmission occurs **without artificial pauses**, following Bluetooth socket readiness or USB transfer completion. Each copy ends with **`1B 69` followed by `1B 4A 00`**, ensuring printing completes before feeding. This ordering applies to all modes; media type is configured separately.

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

## CUPS Printing Integration

You can integrate the E210 with CUPS to use it as a native system printer from browsers, LibreOffice, GIMP, label software, and standard commands like `lp` and `lpr`.

### Installing CUPS Driver

Run the following command in an interactive terminal (for example Konsole), where `sudo` can ask for your password. A non-interactive command runner cannot read the password.

Run the installer with root privileges:

```bash
sudo ./tools/install_cups.sh
```

This installs:
- PPD definition: `/usr/share/cups/model/e210.ppd`
- CUPS raster filter: `/usr/lib/cups/filter/rastertoe210`
- CUPS Bluetooth/USB backend: `/usr/lib/cups/backend/e210`
- Configures and enables printer queue `E210`. A new installation defaults to Bluetooth (`e210://auto`); updates preserve its existing connection.

To install or switch the queue to USB:

```bash
sudo ./tools/install_cups.sh --usb
```

To switch back to Bluetooth, use `--bluetooth`. USB uses `e210://usb` to
select the only connected matching printer. For multiple printers, set an
explicit URI, noting that device numbers change on reconnect:

```bash
sudo lpadmin -p E210 -v e210://usb/001/028
```

The custom `e210://usb` backend sends the same filtered QLabel commands as
Bluetooth. Do not select CUPS' generic `usb://` connection for this setup; it
does not select our backend. No TSPL or Windows driver is involved.

### Printing with CUPS

Print a document or image using default settings (50 mm continuous roll, density 6):

```bash
lp -d E210 document.pdf
```

Print to die-cut gap labels (e.g., 50 × 50 mm) with increased darkness:

```bash
lp -d E210 -o PageSize=50x50mm -o MediaType=Gap -o Darkness=8 label.pdf
```

Supported media sizes in the PPD:
- `50x100mm` (Default)
- `50x80mm`, `50x70mm`, `50x50mm`, `30x50mmRotated`
- `40x60mm`, `30x40mmRotated`
- `30x30mm`, `20x30mmRotated`
- `25x38mmRotated` (38 × 25 mm tag)

Page-size identifiers use Adobe/CUPS standard names and exact millimeter-to-point dimensions. A `Rotated` suffix preserves a wider-than-tall physical label, for example `30x50mmRotated` means 50 mm wide × 30 mm high. These identifiers replace the earlier `Continuous50mm`, `Label…`, and `CableWrap` names; reselect the size in saved application print settings after reinstalling. Roll type remains a separate `MediaType` setting.

### Image sizing in GIMP and other applications

The driver defaults to **Image Sizing → Fit Artwork to Label** (`E210Scaling=FitContent`). It removes blank document margins and fits the artwork proportionally within **both** the printable width (up to 384 pixels / 48 mm) **and the selected page height**. This also applies to continuous paper: a 50 × 50 mm page cannot grow taller than 50 mm when an image has large lateral white borders. Narrower artwork stays narrower when the page height is the limiting dimension.

On continuous paper, unused vertical page padding is removed after fitting. On sensor labels, the full physical page height is preserved so the next label can be positioned. Use **Media Type → Continuous Paper** for a continuous roll, including when **Media Size → 50 × 50 mm** is selected. Use die-cut/gap mode only with actual gaps between labels. Page size limits the layout; media type controls paper positioning. A short physical presentation feed may still occur when the printer becomes idle.

Artwork narrower than the 48 mm head is **right-aligned**, matching the printer's paper guide, rather than centered. Narrow document pages in **Preserve Document Size** mode are also positioned against the right edge; their internal layout is preserved. This applies to continuous, gap and black-mark media.

For example, a 384-pixel PNG tagged as 300 dpi is only 32.5 mm wide in GIMP at its original physical scale. The direct PNG script instead uses 48 mm. The content-fitting option avoids that discrepancy without modifying the source image's DPI metadata.

To preserve a document's physical scale instead, select **Image Sizing → Preserve Document Size** (`E210Scaling=ActualSize`). Content outside the 48 mm head is clipped rather than shrinking the entire physical page. Continuous paper still removes empty leading/trailing rows; use fixed label media when the full page length matters.

```bash
lp -d E210 -o MediaType=Continuous -o E210Scaling=FitContent image.pdf
lp -d E210 -o PageSize=50x50mm -o MediaType=Gap -o E210Scaling=FitContent label.pdf
```

Choose the **page size** and **media type** separately: selecting a 50 × 50 mm page does not itself mean the roll has gaps. The filter honors the media type in the raster header and decodes compressed CUPS/PWG raster through the installed `libcups` library.

After updating the driver, run `sudo ./tools/install_cups.sh` again and reopen GIMP's print dialog so it reloads the PPD and its Image Sizing choices. The installer replaces the filter and updates the existing E210 queue.

Bluetooth discovery uses a known E210 address immediately, or stops scanning as soon as a single active E210 is detected rather than waiting for the full scan timeout. Connection to an already known address skips inquiry. The connection timeout is an upper limit for failures, not a mandatory delay before printing.

To uninstall the CUPS driver and remove the queue:

```bash
sudo ./tools/uninstall_cups.sh
```

## Thermal Density Calibration

The printer hardware accepts density values from 0 to 16. However, physical testing showed that practical contrast begins at level 5, reaches optimal darkness between 6 and 10, plateaus between 10 and 15, and level 16 severely degrades (washing out due to thermal duty-cycle throttling).

You can print a full 1–16 calibration strip to inspect your unit's thermal output:

```bash
# Preview the strip without printing:
python tools/density_test.py --dry-run --preview /tmp/density_test.png

# Print calibration strip directly to E210:
python tools/density_test.py
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
