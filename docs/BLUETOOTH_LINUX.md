# Bluetooth Diagnostics with BlueZ

## Current Validated Behavior

The current sequence for each copy is `configuration → raster → 1B 69 → 1B 4A 00`, without artificial pauses by default and without additional wait before completion. This ordering applies to all media types; command `1C 25 n` continues to distinguish between continuous, gap, and black-mark media. Feed behavior on sensor-equipped labels should be reconfirmed after this change. The sections below preserve the investigation history, including the initial sequence extracted from Java that was superseded after physical testing.

Decisive test on continuous media: twenty consecutive staircases of twenty steps (400 steps of 1 mm total), 87,160 bytes, transmitted without artificial pauses with the final two commands inverted relative to the APK. The user confirmed all were complete and seamlessly joined. Mechanism pauses occurred during execution, with no observed data loss. This validates this workflow, but does not measure the internal buffer capacity, as transport flow control can throttle delivery while the printer processes data.

Prior to that, printing the staircase pattern without final commands exposed only up to the start of step 15. Sending `1B 4A 00` alone advanced the paper, and subsequently sending `1B 69` printed the remainder. Two staircases terminated only with `1B 69` were printed joined, but with fifteen steps each; with `1B 69` followed by `1B 4A 00`, both had twenty full steps. The full semantics of each command remain to be formally established. An isolated staircase finished with a paper feed; the hypothesis that the printer feeds to tear-off position when entering idle is consistent with observations, but is not confirmed as a firmware rule.

Local logs: `captures/print-staircase-no-final.jsonl`, `captures/staircase-final-command-1b4a00.jsonl`, `captures/staircase-final-command-1b69.jsonl`, `captures/print-two-staircases-no-feed.jsonl`, `captures/print-two-staircases-reversed-final.jsonl`, `captures/print-staircase-separated-first.jsonl`, and `captures/print-20-staircases-continuous.jsonl`.

We use the standard BlueZ D-Bus APIs `Adapter1`, `ProfileManager1`, `Profile1`, and `Device1.ConnectProfile`, without deprecated tools like `sdptool` or `rfcomm`.

The client registers an outbound serial profile with UUID `00001101-0000-1000-8000-00805f9b34fb`. BlueZ discovers the remote service and delivers a connected socket file descriptor via the `Profile1.NewConnection` callback. This eliminates the need to configure or select an RFCOMM channel manually.

Official documentation:

- https://bluez.readthedocs.io/en/latest/profile-api/
- https://bluez.readthedocs.io/en/latest/device-api/

## Native Dependencies

On CachyOS/Arch: active BlueZ service, Python, `python-dbus`, and `python-gobject`. The Python bindings were already present in the initial test environment. If missing, install them through system package managers.

## Usage

Power on the E210 and terminate any existing connections from other devices. Obtain the printer's Bluetooth address via discovery, for instance using `bluetoothctl`. Making the host computer discoverable is not required.

Connect only:

```bash
python tools/probe_bluez.py BLUETOOTH_ADDRESS
```

Connect and send the settings query identified in the app:

```bash
python tools/probe_bluez.py BLUETOOTH_ADDRESS --query --timeout 25
```

Other queries identified in the Java helper:

```bash
python tools/probe_bluez.py BLUETOOTH_ADDRESS --query status --timeout 20
python tools/probe_bluez.py BLUETOOTH_ADDRESS --query model --timeout 20
```

`--query` without a value defaults to `settings`. The supported query options are `settings`, `status`, and `model`; arbitrary command injection is not supported. The tool logs raw bytes: receiving bytes does not necessarily mean the response is complete or semantically valid.

The timeout spans discovery, connection, and reception. Output is formatted as JSON per event. Query modes do not print; printing requires `--print-test`. The client does not modify the `Trusted` property. Upon completion, it closes the socket, stops discovery, and unregisters the temporary profile. The exit code is non-zero if connection fails or if a query finishes without a response.

## First Physical Test — 2026-10-20

- Printer discovered under name `E210`.
- Serial Port service advertised with the UUID expected by Java code.
- BlueZ 5.87; `dbus` and `gi` bindings already installed.
- Client profile registration and D-Bus connection succeeded.
- Received socket indicated remote RFCOMM channel **1** on this unit.
- Query `1B 5E` sent 300 ms after connection established.
- Zero bytes received before the 25-second overall timeout expired.
- No print commands were sent.

The specific hardware unit address is omitted from public documentation. The observed RFCOMM channel should not be hardcoded as constant for all units; BlueZ dynamic service discovery should always be used.

The test confirmed serial connectivity, but did not confirm a full protocol handshake. Next steps: test status and model queries present in the helper and compare against real QLabel traffic, capturing raw bytes and timestamps.

## Status and Model Queries — 2026-10-20

Each query was conducted over its own connection via Profile1 on the channel resolved by BlueZ. Overall timeout was 20 seconds per run. No print commands were sent.

| Query | Sent | Received, concatenated through end of test | Result |
| --- | --- | --- | --- |
| Status | `1B 06` | `1B 06 00 03` | Bidirectional communication confirmed |
| Model | `1B 18` | `1B 18` | Prefix only; model identification not received |

The `getPrintStatus` helper reads byte index 2, which is `00` in this response. We do not assign semantics to the trailing `03` byte nor declare the printer ready: controlled tests associating fields with physical states are still required.

The Java method `getRDPrinterModel` expects a length byte following `1B 18`, followed by the device name. That field was never received. Therefore, the model response does not conform to the structure expected by that app method. Do not assume all generic SDK commands are supported by the E210 firmware.

Local logs ignored by Git: `captures/probe-status.jsonl` and `captures/probe-model.jsonl`.

Next milestone: prepare a basic raster label following the sequence found in Java, derive dimensions from installed media, and validate physical printing.

## First Raster Transmission — 50 mm Continuous Media

The user indicated 50 mm wide continuous media. A single print job was prepared with nominal length of 20 mm, density 6, zero offsets, and paper type 0. The raster adheres to the Java formula for 50 x 20 mm: 384 x 152 pixels, approximately 48 x 19 mm at the 8 dots/mm scale used by the app.

The pattern consists of a border, a corner square, and three bars of varying heights. `tools/e210_raster.py` generates the raster and command sequence with no third-party dependencies. Tests in `tests/test_raster.py` verify row vectors derived from Java and decode the complete packet back to the original raster.

```bash
python -m unittest discover -s tests -v
python tools/probe_bluez.py BLUETOOTH_ADDRESS --print-test --timeout 25
```

The second command prints once; avoid running repeatedly without need. A successful exit code confirms complete transmission to the socket, not physical printing confirmation.

Local artifacts: `captures/test-50mm-continuous.pbm`, `captures/test-50mm-continuous.bin`, and `captures/print-test-50mm.jsonl`. The initial transmission sent 7,046 bytes to the socket. The user observed only a few dots along a single line, with no perceptible paper feed. **The print test failed**, despite full socket transmission and passing encoder tests.

This result did not distinguish between an unsupported firmware format, incorrect configuration/feed commands, transmission pacing issues, or mechanical media problems. No definitive root cause was found during Java review. The test script batched commands into a single buffer, whereas the mobile app issued distinct write calls for configuration, raster rows, and feeds; this was an area for investigation rather than a proven cause.

## Feed Isolation

A diagnostic mode was added to send only `1B 4A 20`, corresponding to `PrinterHelper.setPrinterPageRun(32)`. The command is present in the APK helper, although the parameter-taking overload was not observed in the primary print path. Its physical units and behavior on the E210 required confirmation.

```bash
python tools/probe_bluez.py BLUETOOTH_ADDRESS --feed-test --timeout 15
```

This test sends no raster data, does not alter configuration, and does not reset the printer. Local log: `captures/feed-test-32.jsonl`. The user confirmed a small paper feed: the command was accepted and physical paper movement occurred. Feed distance was not measured.

## Same Raster with Transmission Pauses

After confirming isolated feed behavior, the original pattern was retransmitted with 20 ms pauses between commands and rows. The objective was to test for socket reception/processing rate limits without altering job content. The payload was the identical 7,046 bytes in 160 chunks: six configuration commands, 152 rows, and two final commands.

Automated tests confirm that concatenating these chunks reproduces the original packet identically. Separate write calls do not guarantee packet boundaries over RFCOMM: pauses were the experimental variable.

```bash
python tools/probe_bluez.py BLUETOOTH_ADDRESS --paced-print-test --timeout 25
```

Socket transmission completed. The user confirmed printing of the border, square, and three bars of increasing heights, matching the generated raster. This was the first successful physical print. The result supports the pacing rate-limit hypothesis, without yet determining the minimum reliable pause. Local log: `captures/print-test-paced.jsonl`.

## PNG Printing

`tools/print_png.py` processes PNG files via `tools/png_job.py` and reuses the BlueZ connection from diagnostics. Defaults are 384-pixel raster width, preserved aspect ratio, 50 mm continuous media, and density 6. Transparency is composited over white, followed by resizing and monochrome conversion. Options exist for preview, fixed thresholding, and dry-run preparation without printing. Refer to README for usage examples.

The local file `teste.png` was transmitted via the PNG interface as a 384 × 384 pixel raster (48 × 48 mm), totaling 11,713 bytes. The user confirmed the print completed flawlessly. The user-provided file remains local and untracked. Local log: `captures/print-teste-png.jsonl`.

## Gap Labels and Copies

Java review: `EditSetActivity.ZZClick.onClick` maps label gap selection to `paperType = 2`, black mark to `3`, and continuous to `0`. `PrintActivity` builds page/copy lists, and `LPBTService.startToPrint` iterates over these pages. Each `printImage` configures paper type and concludes with `1B 4A 00` and `1B 69` before moving to the next page.

The Python CLI accepts `--media`, `--label-height`, and `--copies`. Multiple copies are produced by repeating the full print job. Paper dimensions are kept distinct from raster dimensions: a 48 × 48 mm image can target a 50 × 50 mm logical label.

After the user changed media, a three-copy test was requested. The media was assumed to be 50 × 50 mm gap labels, as dimensions and sensor calibration had not yet been measured. Job: `teste.png`, 384 × 384 raster, `1C 25 02`, logical dimensions 500/500 in tenths of a mm, three pages, 35,139 bytes. Local log: `captures/print-gap-three-copies.jsonl`. Physical count and alignment remain subject to user confirmation.

## Pacing Comparison on Solid Black Block

On continuous paper, a fully black block of 384 × 400 pixels (48 × 50 mm) was printed at density 10. With 20 ms pauses, the user noted good print quality on the first half followed by motor stuttering on the second half. The same block was then sent with 50 ms pauses, but no explicit physical assessment occurred before the next test.

At the user's request, the block was re-sent with `--pause-ms 0`: the same 21,230 bytes, sequentially without artificial delays. The user confirmed that it **printed better**. This demonstrates an improvement for this unpaused test, but does not prove a thermal, electrical, or buffering cause, nor does it establish that this pacing is optimal for all images.

This finding contrasted with the initial geometric test pattern, which had failed without pauses and succeeded with 20 ms. The subsequent investigation into termination commands resolved the issue, superseding this initial setup with the behavior documented at the start of this file. Local logs: `captures/print-black-48x50mm-density10.jsonl`, `captures/print-black-48x50mm-density10-pause50.jsonl`, and `captures/print-black-48x50mm-density10-pause0.jsonl`.

## Thermal Density Calibration (Levels 1 to 16)

Using `tools/density_test.py`, a full calibration strip covering hardware density levels 1 through 16 was printed on continuous paper. Each block contained black-on-white text with fine lines and an inverted white-on-black solid block.

Observed physical results:
- **Levels 1 to 4**: Very light / faint output, insufficient for everyday contrast.
- **Levels 5 and 6**: Useful density begins here. Level 6 produces clean, sharp text and borders without bleeding, validating it as a well-balanced default.
- **Levels 7 to 10**: Increasingly deep blacks. Level 10 provides solid, high-contrast black fill without motor stutter.
- **Levels 10 to 15**: Output plateaus; visual contrast and darkness remain practically indistinguishable from level 10.
- **Level 16**: Fails severely, fading back to the faintness of level 1. This behavior is consistent with duty-cycle / pulse-width limits, voltage drop, or firmware thermal throttling when maximum heat pulse duration is exceeded.

**Conclusion**: The effective operational density range for the E210 is **5 to 10**, with **6** as standard default and **10** as high-contrast maximum. Level 16 should be avoided.
