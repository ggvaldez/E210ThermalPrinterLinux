# E210 Investigation

## Known Information

| Item | Information | Source |
| --- | --- | --- |
| Reported model | E210 | Initial user report |
| Type | Bluetooth thermal printer | Initial user report |
| App used | QLabel, available on Google Play Store | Initial user report |
| Goal | Direct printing from Linux | Project scope |

## Information to Collect

- Exact printer identification and label dimensions used.
- QLabel Play Store URL and installed version.
- Linux distribution, kernel version, and Bluetooth adapter.
- Advertised printer name and discovery details.
- Bluetooth services and, if using BLE, GATT characteristics and their properties.
- Capture of a successful print session from the mobile app.

## Initial Experiment

Use a label with simple, known content, such as a small image with a border and the text `E210 Linux`. Record file and label dimensions and the options selected in the app.

Then compare two print jobs that vary only one parameter at a time, such as content, width, or number of copies. Preserve packet order and transmission timing to investigate fragmentation and flow control.

The capture method will be chosen based on the available phone and transport. At this stage, there is not yet enough capture data or evidence to specify all print commands.

## Record for Each Test

```text
Date:
Device / firmware:
System / Bluetooth adapter:
App / version, when applicable:
Objective:
Procedure and commands:
Input and settings:
Expected result:
Observed result:
Associated artifacts:
Confirmed conclusions:
Hypotheses and next experiment:
```

## Proof of Concept Success Criteria

A label sent from Linux must print with expected content and dimensions. The procedure must be repeatable after disconnecting and reconnecting the printer, without relying on the mobile app during printing.


## USB and alternative-driver findings (2026-10-21)

The physical E210 exposes USB VID/PID `08c5:4001`, manufacturer YICHIP,
product `YC3121 Printer demo`. It has one Printer Class interface (0),
bulk OUT endpoint `0x01` and interrupt IN endpoint `0x81`, with 64-byte
maximum packets. Its IEEE-1284 ID only reports `printer;`.

The existing QLabel byte stream printed correctly over USB. The integrated
PNG command was physically validated with automatic USB discovery, density
6 and a 384 by 384 dot image. USB transport uses the system libusb directly;
no serial node or BlueZ service is required for this path.

Two seller tutorials ([original](https://www.youtube.com/watch?v=hKj7dEjKjf0),
[updated](https://www.youtube.com/watch?v=8qNW0WJvkj4)) recommend the Windows
TSC TDP-245 driver for a branded XD-210/PT-260. Their linked TSC 7.3.4.5
package was inspected statically and with Ghidra. A temporary Wine harness
executed original renderer functions for raw BITMAP and binary !R/!S
formats, using a small known pattern and explicit setup commands. None
produced a reaction on our unit, although USB transfers completed.

Those experiments did not reproduce the complete Windows print pipeline
or capture its actual initialization. They do not establish that every
TSPL variant is unsupported, nor that the seller's unit has the same
firmware. TSPL support is therefore unconfirmed and is not implemented.
Temporary Windows installers, Wine/Ghidra projects and experimental
harnesses were removed after recording these findings. The validated
implementation continues to use the QLabel protocol for both transports.
