# Intrepid CAN Message Capture

This project contains a Python utility for monitoring messages from the first available Intrepid device and exporting them to log files in `BLF` and/or `VSB` format.

The script is implemented in `get_message.py` and is intended for CAN traffic capture workflows using the Intrepid ICS API (`ics`) plus `python-can` and the VSB writer utilities provided in this project.

## What it does

- Detects the first Intrepid ICS device returned by `ics.find_devices()`
- Opens the device and continuously reads incoming messages
- Converts each message into a `can.Message` for BLF export
- Writes VSB output through `VSBWriter`
- Optionally stops automatically by checking a config file for a non-zero `stop` flag
- Supports graceful stop with `Ctrl+C`

## Requirements

Before running the script, make sure the following are available:

- Python 3.x
- `ics` package from the Intrepid API
- `python-can` package
- `ics_vsbio_private` package
- A connected Intrepid device recognized by the ICS driver

## Usage

```bash
python get_message.py --output_file <base_name_or_path> --output_format <blf|vsb|all> --config_file <path_to_config>
```

### Arguments

- `--output_file`, `-o` (required): base file name/path used for generated log files
- `--output_format` (optional, default: `blf`): output format to generate
  - `blf`: writes `<output_file>.blf`
  - `vsb`: writes `<output_file>.vsb`
  - `all`: writes both `.blf` and `.vsb`
- `--config_file`, `-c` (required): INI-style config file used to signal when monitoring should stop

If `--output_format` is not one of `vsb`, `blf`, or `all`, the script exits with:

```text
Only vsb, blf and all are accepted
```

## Example

Generate a BLF capture file:

```bash
python get_message.py -o logs\lin_capture --output_format blf --config_file stop.ini
```

Generate a VSB capture file:

```bash
python get_message.py -o logs\lin_capture --output_format vsb --config_file stop.ini
```

Generate both formats:

```bash
python get_message.py -o logs\lin_capture --output_format all --config_file stop.ini
```

## Stop configuration

The script monitors the config file every second. If the config contains a non-zero `stop` value, monitoring stops automatically.

Example `stop.ini`:

```ini
[monitor]
stop = 0
```

or:

```ini
[DEFAULT]
stop = 0
```

When `stop` becomes `1` or any non-zero value, the loop exits and prints:

```text
Monitoring stopped.
```

You can also stop the capture manually at any time with `Ctrl+C`.

## Output behavior

The script writes log files using the configured output format:

- `BLF`: written using `can.BLFWriter`
- `VSB`: written through `VSBWriter`
- `all`: both are generated

The monitor reads message timestamps and converts the data to a `can.Message` for BLF output while preserving raw message information for VSB output.

## Notes

- The script always targets the first device found by `ics.find_devices()`.
- It does not support selecting a specific device by serial number or port through CLI arguments.
- The `ASC` writer logic is present in the code but is currently disabled in the main capture loop.
- This tool is primarily for LIN message capture and export; it is not a general-purpose GUI or visualization application.

## Typical workflow

1. Connect the Intrepid device.
2. Create a config file with `stop = 0`.
3. Run the capture script with the desired output format.
4. Let the device capture traffic.
5. Set the config file value to a non-zero number to stop the logger, or use `Ctrl+C`.

## License

This project is distributed under the repository's existing license. See `LICENSE` for details.
