import ics
import can
from ics_vsbio_private.ICS_VSBIO.VSBWriter import VSBWriter
from ics_vsbio_private.ICS_VSBIO.VSBReader import VSBMessage
from ics_vsbio_private.ICS_VSBIO import VSBIOInterface as vsb
from datetime import datetime
import argparse
import time
import subprocess
import os
import sys
import threading
import configparser


_VSB_SCALAR_FIELDS = (
    'StatusBitField', 'StatusBitField2', 'StatusBitField3', 'StatusBitField4',
    'TimeHardware', 'TimeHardware2', 'TimeSystem', 'TimeSystem2',
    'TimeStampHardwareID', 'TimeStampSystemID',
    'NetworkID', 'NetworkID2', 'NodeID', 'Protocol', 'MessagePieceID',
    'ExtraDataPtrEnabled', 'NumberBytesHeader', 'NumberBytesData',
    'DescriptionID', 'ArbIDOrHeader', 'MiscData',
)

def _spy_to_vsb_message(spy_msg):
    """Convert an ics.SpyMessage to a VSBMessage for use with VSBWriter."""
    m = vsb.icsSpyMessageVSB()
    for attr in _VSB_SCALAR_FIELDS:
        if hasattr(spy_msg, attr):
            try:
                setattr(m, attr, getattr(spy_msg, attr))
            except Exception:
                pass
    try:
        for i in range(8):
            m.Data[i] = spy_msg.Data[i]
    except Exception:
        pass
    return VSBMessage(m, None, vsb.icsSpyMessageVSB_SIZE)


# Maps ics LIN network IDs to 1-based channel numbers used in ASC files.
_LIN_CHANNEL_MAP = {}


def _build_timestamped_path(output_file):
    if not output_file:
        return None
    base_name, extension = os.path.splitext(output_file)
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    if extension:
        return f'{base_name}_{timestamp}{extension}'
    return f'{base_name}_{timestamp}'


def _build_lin_channel_map():
    for attr, channel in [('NETID_HSCAN', 1), ('NETID_HSCAN2', 2), ('NETID_LIN', 3)]:
        if hasattr(ics, attr):
            _LIN_CHANNEL_MAP[getattr(ics, attr)] = channel

_build_lin_channel_map()


class AscWriter:
    """Writes LIN messages to a CANalyzer-compatible ASC log file."""

    def __init__(self, filename):
        self.filename = filename
        self._file = None
        self._prev_timestamp = None

    def open(self):
        self._file = open(self.filename, 'w')
        now = datetime.now()
        self._prev_timestamp = None
        self._file.write('date {}\n'.format(now.strftime('%a %b %d %H:%M:%S.%f %Y')))
        self._file.write('base hex  timestamps absolute\n')
        self._file.write('no internal events logged\n')
        self._file.flush()

    def write_message(self, device, msg):
        if self._file is None:
            return

        timestamp = ics.GetTimeStampForMsg(device, msg)
        if self._prev_timestamp is None:
            rel_time = 0.0
        else:
            rel_time = timestamp - self._prev_timestamp
        self._prev_timestamp = timestamp

        channel = _LIN_CHANNEL_MAP.get(msg.NetworkID, 1)
        id = msg.ArbIDOrHeader  # raw LIN ID (0–63)
        dlc = msg.NumberBytesData
        data_str = ' '.join('{:02X}'.format(b) for b in msg.Data[:dlc])
        direction = 'Tx' if (msg.StatusBitField & ics.SPY_STATUS_TX_MSG) else 'Rx'

        self._file.write('   {:.6f} {}  {:03X}  {}  d  {}  {}\n'.format(
            rel_time, channel, id, direction, dlc, data_str))
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


class LinMonitor:
    def __init__(self, output_file=None, output_format='blf', config_file=None):
        devices = ics.find_devices()
        for device in devices:
            print(device.Name, device.serial_number)

        if len(devices) == 0:
            raise RuntimeError('No ICS devices found')

        self.device = ics.open_device(devices[0])
        self.output_file = output_file
        self._asc_writer = AscWriter(_build_timestamped_path(output_file + '.asc')) if output_file else None
        self.output_format = output_format
        self.vsb_filename = os.path.abspath(_build_timestamped_path(output_file + '.vsb')) if output_file else None
        self.blf_filename = os.path.abspath(_build_timestamped_path(output_file + '.blf')) if output_file else None
        self.config_file = config_file
        # print('config_file: {}'.format(self.config_file))
        self._stop_requested = threading.Event()

    def _read_config_value(self, key, default=0):
        if not self.config_file:
            return default
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f'Config file not found: {self.config_file}')

        try:
            config = configparser.ConfigParser()
            config.read(self.config_file, encoding='utf-8')
            for section_name in ('monitor', 'DEFAULT'):
                if config.has_option(section_name, key):
                    return int(config.get(section_name, key))
            return default
        except Exception as exc:
            raise RuntimeError(f'Failed to read config file {self.config_file}: {exc}') from exc

    def _read_stop_value(self):
        return self._read_config_value('stop', 0)

    def _read_exit_value(self):
        return self._read_config_value('exit', 0)

    def _should_pause(self):
        if not self.config_file:
            return False
        try:
            return self._read_stop_value() != 0 and self._read_exit_value() == 0
        except Exception as exc:
            print(f'Error reading config file: {exc}', file=sys.stderr)
            return False

    def _should_exit(self):
        if not self.config_file:
            return False
        try:
            return self._read_exit_value() != 0
        except Exception as exc:
            print(f'Error reading config file: {exc}', file=sys.stderr)
            return False

    def monit(self):
        print('monitoring')
        blf_writer = can.BLFWriter(self.blf_filename) if self.output_format in ('blf', 'all') else None
        vsb_writer = VSBWriter(self.vsb_filename) if self.output_format in ('vsb', 'all') else None
        stopped_by_user = False
        # self._asc_writer.open()
        # print('Logging to {}'.format(self._asc_writer.filename))

        try:
            while True:
                if self._stop_requested.is_set() or self._should_exit():
                    stopped_by_user = True
                    break
                if self._should_pause():
                    time.sleep(0.1)
                    continue

                msgs, error_count = ics.get_messages(self.device)
                for item in msgs:
                    if self._stop_requested.is_set() or self._should_exit():
                        stopped_by_user = True
                        break
                    if self._should_pause():
                        break
                    if vsb_writer is not None:
                        vsb_writer.write_msg(_spy_to_vsb_message(item))
                    if blf_writer is not None:
                        dlc = int(item.NumberBytesData)
                        is_extended = bool(item.StatusBitField & ics.SPY_STATUS_XTD_FRAME)
                        is_remote = bool(item.StatusBitField & ics.SPY_STATUS_REMOTE_FRAME)
                        is_rx = not bool(item.StatusBitField & ics.SPY_STATUS_TX_MSG)
                        is_fd = bool(item.Protocol == getattr(ics, 'SPY_PROTOCOL_CANFD', item.Protocol)) or bool(item.StatusBitField & getattr(ics, 'SPY_STATUS_CANFD', 0))
                        bitrate_switch = bool(getattr(item, 'StatusBitField3', 0) & getattr(ics, 'SPY_STATUS3_CANFD_BRS', 0))
                        error_state_indicator = bool(getattr(item, 'StatusBitField3', 0) & getattr(ics, 'SPY_STATUS3_CANFD_ESI', 0))
                        timestamp = float(ics.GetTimeStampForMsg(self.device, item))
                        channel = _LIN_CHANNEL_MAP.get(item.NetworkID, 0)
                        payload = bytes(item.Data[:dlc]) if item.ExtraDataPtrEnabled == 0 else bytes(item.ExtraDataPtr[:dlc])
                        can_msg = can.Message(
                            timestamp=timestamp,
                            arbitration_id=int(item.ArbIDOrHeader),
                            is_extended_id=is_extended,
                            is_remote_frame=is_remote,
                            is_rx=is_rx,
                            dlc=dlc,
                            data=payload,
                            channel=channel,
                            is_fd=is_fd,
                            bitrate_switch=bitrate_switch,
                            error_state_indicator=error_state_indicator,
                        )
                        blf_writer.on_message_received(can_msg)
                    # self._asc_writer.write_message(self.device, item)

                if stopped_by_user:
                    break

                time.sleep(0.01)
        except KeyboardInterrupt:
            stopped_by_user = True
        finally:
            self._stop_requested.set()
            if vsb_writer is not None:
                vsb_writer.close()
            if blf_writer is not None:
                blf_writer.stop()
        if stopped_by_user:
            # self._asc_writer.close()
            print('Monitoring stopped.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output_file', '-o', required=True, help='the data file to be generated')
    parser.add_argument('--output_format', default='blf',
                        help='output format: blf, vsb, all')
    parser.add_argument('--config_file', '-c', required=True, help='The yaml config file in to read the stop signal')
    args = parser.parse_args()
    if args.output_format not in ('vsb', 'blf', 'all'):
        raise ValueError('Only vsb, blf and all are accepted')
    try:
        monitor = LinMonitor(args.output_file, args.output_format, args.config_file)
        monitor.monit()
    except RuntimeError as e:
        print(f'Error: {e}')
