# Java Analysis of QLabel 29.0.22

## Origin and Scope

- Package: `com.rmicro.labelprinter`.
- APK: `captures/apk/QLabel_29.0.22.apk`, obtained from APKPure.
- SHA-256: `7428e16ac3c70e6ff412ff1fdb5e14dbfab4e76c019dc1a19f06c44b4f90fabe`.
- Tool: JADX 1.5.6. For future tools, check CachyOS repositories and the AUR and request native installation from the user before downloading standalone distributions.
- Local sources: `captures/decompiled/qlabel/sources/`.
- Decompilation command: `jadx -j 2 --no-res -d captures/decompiled/qlabel captures/apk/QLabel_29.0.22.apk`.
- The original decompilation finished with 111 errors reported by JADX; the log is in `captures/decompiled-jadx.log`. This does not imply all methods were recovered correctly. The methods below have available Java bodies, but were not yet compared against Bluetooth captures or execution on the physical E210.

These conclusions describe the behavior of the analyzed application. Physical printer validation is required. The names of certain operations originate from the application and do not represent official manufacturer specifications.

## Path Serving the E210

References relative to the decompiled sources root:

| Step | Evidence |
| --- | --- |
| Model name | `com/yundayin/templet/Constant.java:16`: `E210 = "E210"` |
| Transport selection | `com/rmicro/labelprinter/main/view/activity/ConnectionListActivity.java:367`: names starting with `E2` enter `connectPrinterByAddressForYP1` |
| Connection by address | `com/rmicro/labelprinter/bluetooth/LPBTService.java:1034`: delegates to `BluetoothSdkManager.connect` |
| Socket | `com/rmicro/labelprinter/yp1sdk/service/BtService.java:231`: `createRfcommSocketToServiceRecord` |
| UUID | `com/rmicro/labelprinter/yp1sdk/constant/ConstantDefine.java:28`: `00001101-0000-1000-8000-00805F9B34FB` |
| Printing | `com/rmicro/labelprinter/bluetooth/LPBTService.java:525`: connections using this SDK route to `printImage` |
| Encoding and commands | `com/rmicro/labelprinter/yp1sdk/util/PrinterHelper.java` |

Therefore, the path identified for a device advertised as E210 uses Classic Bluetooth via RFCOMM and the Serial Port Profile UUID. The numeric RFCOMM channel is not specified in this constant: it must be discovered dynamically from the actual unit's service records. Do not assume channel 1.

The application also includes BLE and other SDKs, but their presence does not imply they are used by the E210.

## Connection and Reception

`LPBTService.initSDKManager` schedules `sendCheckMessage` 300 ms after the SDK reports a connected state. This method sends `1B 5E`.

The receiver identifies prefixes `1B 1E` and `1B 5E` and invokes `parseData`. The third byte is interpreted as state: `01`, `FF`, `FE`, and `FD` map to internal states. There is insufficient evidence to attribute all these values to specific physical conditions.

For state `01`, `parseEN13` parses a variable-length identification field and media data: type, width, and height in tenths, angle, material, color, and length. This suggests communication regarding the consumable, but does not prove authentication requirements or label locking.

`showOptins` sends `1B 1E 01` as a response on certain transitions. Isolated bytes `E1` through `E8` are treated as print failures by the callback.

Reading from the socket delivers currently available bytes without rigid message framing. A Linux implementation must handle fragmented or coalesced messages rather than assuming each read corresponds to an entire response.

## Observed Print Sequence

In `LPBTService.printImage`, line 1539 onwards:

1. Configures density, horizontal and vertical offsets, and paper type.
2. Resizes image and converts to monochrome.
3. Sends `1B 33`, named `setPrinterForAndroid` by the SDK.
4. Configures dimensions and raster height via `setPrinterLabelParam`.
5. Sends encoded rows produced by `getTargetPrintData`.
6. Sends `1B 4A 00` followed by `1B 69`, described in code as adjust and feed to next page.

| Operation in Java | Hexadecimal bytes |
| --- | --- |
| Query settings / consumable | `1B 5E` |
| Acknowledge notification | `1B 1E 01` |
| Status query available in helper | `1B 06` |
| Model query available in helper | `1B 18` |
| Density | `1C 21 n` |
| Paper type | `1C 25 n` |
| Vertical offset | `1B 34 sign magnitude` |
| Horizontal offset | `1B 35 sign magnitude` |
| Mode named "Android" | `1B 33` |
| Label parameters | `1B 29 rasterHeightLE16 dimension1LE16 dimension2LE16 flags` |
| Image row | `1B 19 01 (N+1) offset payload` |
| Feed adjustment | `1B 4A 00` |
| Next page | `1B 69` |

In code, negative offsets become sign `1` and non-negative offsets become `0`; magnitude is sent in one byte. The physical unit of the offset remains to be measured. The density method constrains values between 0 and 16.

The application describes paper types as: `0` continuous, `1` positioning hole, `2` label gap, `3` black mark, and `4` cable label. This must be validated for the specific model.

The helper includes CPCL methods and other commands not used in this raster sequence. Do not classify the overall E210 protocol as CPCL, TSPL, or ESC/POS solely based on these helper methods or the ESC prefix.

## Dimensions and Pixels

`printImage` accepts two dimension values whose order depends on orientation in `drawBitmap`; decompiled variable names are ambiguous. To avoid swapping width and height, validate a rectangular label and its orientation first.

The application uses the following calculations:

- `d1 = int(first dimension)`; `r = min(d1, 48)`.
- Sent bitmap width: `r * 8` pixels.
- Bitmap height: `int(r * second dimension / first dimension) * 8` pixels.
- Label parameters: `d1 * 10`, `int(second dimension) * 10`, `bitmap height + 1`, `0`.
- In packet `1B 29`, raster height precedes the two dimensions, all encoded as 16-bit little-endian.

This indicates an 8 dots/mm scale and a 384-pixel limit on raster width along this application path. It does not constitute a direct measurement of the physical resolution or print head width.

`getBitmapData_Y` calls `removeAlpha`, `sDither`, and `get8BitDataH`. The final layout is horizontal, row by row, with eight pixels per byte, leftmost pixel in the most significant bit, white as `0` and black as `1`. Remaining bits in the final byte are zero-padded.

## Per-Row Format

In `PrinterHelper.getTargetPrintData` (line 1023) and `getImageCmd1B19` (line 1520):

- Trims `00` bytes from row start and end.
- `offset` is the count of bytes trimmed from the start, not pixels.
- `N` is the count of remaining payload bytes.
- Header is `1B 19 01 (N+1) offset`.
- A fully blank row also includes a header: `N = 0` and `offset = width_in_bytes`.
- Rows are concatenated without extra delimiters in this method.

Examples derived from the algorithm, prior to printer verification:

| Row raster | Packet |
| --- | --- |
| `00 80 01 00` | `1B 19 01 03 01 80 01` |
| `00 00 00 00` | `1B 19 01 01 04` |
| `FF FF FF FF` | `1B 19 01 05 00 FF FF FF FF` |

## Transmission and Native Dependencies

`PrinterHelper.WriteData` delegates to `BluetoothSdkManager.print`, which maintains a queue and sends via `BtService`. `ConnectedThread.write` writes the array to `OutputStream` and calls `flush`. There is no BLE fragmentation, per-row acknowledgment, or explicit per-row delay along this path. This does not guarantee that the printer tolerates unthrottled streaming or that response reading can be omitted.

All traced raster assembly and configuration methods are implemented in Java. No calls to `libPrinterNative.so` were found in these methods; native library analysis is unnecessary for initial implementations based on this path. Additional commands may occur when labels contain special elements such as barcodes (`scaleImage` also invokes `drawOneCode`). Start proof of concept with a simple raster image.

## Next Validation Steps

1. Discover the unit on Linux, record advertised name and RFCOMM service/channel.
2. Connect and observe the response to query `1B 5E`.
3. Compare, if possible, against a packet capture of QLabel printing a known rectangular label.
4. Implement the encoder and a basic raster print with explicit dimensions and response handling.
5. Confirm orientation, boundaries, feed behavior, and error handling on physical hardware.
