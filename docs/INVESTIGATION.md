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
