# Intrepid LIN Message Capture

This project contains a Python utility for monitoring messages from the first available Intrepid device and exporting them to log files in `BLF` and/or `VSB` format.

The script is implemented in `get_message.py` and is intended for LIN traffic capture workflows using the Intrepid ICS API (`ics`) plus `python-can` and the VSB writer utilities provided in this project.

## What it does

- Detects the first Intrepid ICS device returned by `ics.find_devices()`
- Opens the device and continuously reads incoming messages
- Saves output files with a filename timestamp in the format:
  `filename_YYYY_MM_DD_hh_mm_ss.blf`
- Converts each message into a `can.Message` for BLF export
- Writes VSB output through `VSBWriter`
- Monitors an INI config file for `stop` and `exit` control flags
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
  - `blf`: writes `<output_file>_YYYY_MM_DD_hh_mm_ss.blf`
  - `vsb`: writes `<output_file>_YYYY_MM_DD_hh_mm_ss.vsb`
  - `all`: writes both `.blf` and `.vsb` with timestamped filenames
- `--config_file`, `-c` (required): INI-style config file used to control capture state

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

## Stop and exit behavior

The script checks the config file every second. Supported keys are:

- `stop = 0`: continue monitoring and writing to the output file
- `stop = 1`: stop reading new data from the bus but keep the current file open and saved; the script does not exit
- `exit = 1`: save the current data and exit the script

Example `stop.ini`:

```ini
[monitor]
stop = 0
exit = 0
```

or:

```ini
[DEFAULT]
stop = 0
exit = 0
```

When `exit` becomes `1`, the script closes the writer(s) and prints:

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
- `ASC` support is present in the code base, but the active capture path is the BLF/VSB workflow used by the script.
- This tool is primarily for LIN message capture and export; it is not a general-purpose GUI or visualization application.

## Typical workflow

1. Connect the Intrepid device.
2. Create a config file with `stop = 0` and `exit = 0`.
3. Run the capture script with the desired output format.
4. Let the device capture traffic.
5. Set `stop = 1` to pause monitoring, or set `exit = 1` to save and exit.

## License

This project is distributed under the repository's existing license. See `LICENSE` for details.
