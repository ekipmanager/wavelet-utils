import sys
import time
from datetime import datetime
import struct as st
from gattlib import *
from pyprind import ProgBar
from threading import Event

from cutils.sensors.converter import get_log_count
from wed_settings import *


class Requester(GATTRequester):
    def __init__(self, wake_up, *args):
        GATTRequester.__init__(self, *args)
        self.wake_up = wake_up
        self.log_count = 0
        self.done = False
        self.max_logs = 50
        self.file = None
        self.next_print = 0
        self.print_step = 200

    def on_notification(self, handle, data):
        self.log_count += get_log_count(data[3:])
        if self.log_count > self.max_logs:
            if not self.done:
                self.done = True
                self.wake_up.set()
        self.file.write(data[3:])
        if self.log_count > self.next_print:
            self.next_print += self.print_step
            self.wake_up.set()


class DeviceInterface:
    def __init__(self, mac_address, command, backend_lock,
                 device_settings=None,
                 log_stream=None,
                 fname=None,
                 raw=False,
                 wake_up=None,
                 stop_event=None):

        self.mac_address = mac_address
        self.fname = fname
        if self.fname is None:
            self.fname = "./data/WED_data"
        self.command = command
        self.raw = raw
        self.backend_lock = backend_lock
        if log_stream is None:
            self.log_stream = sys.stdout
        else:
            if not (hasattr(log_stream, 'write') and hasattr(log_stream, 'flush')):
                raise ValueError("No Valid stream found")
            self.log_stream = log_stream

        self.daemon = True

        if device_settings is None:
            self.device_settings = AmiigoSettings()
        else:
            self.device_settings = device_settings

        # Initialize configs
        self.status = None
        self.total_logs = 0
        self.config = None
        self.sample_period = None
        if stop_event is None:
            self._stop = Event()
        else:
            self._stop = stop_event

        if wake_up is None:
            self.received = Event()
        else:
            self.received = wake_up

        self.requester = Requester(self.received, mac_address, False)

    @property
    def stopped(self):
        return self._stop.is_set()

    def is_connected(self):
        return self.requester.is_connected()

    def run(self):
        self.connect()
        self.read_status()

        if self.command == Commands.DOWNLOAD:
            self.wait_notification()
        elif self.command == Commands.BLINK:
            self.blink()
        elif self.command == Commands.STATUS:
            self.print_status()

        self.disconnect()

    @property
    def battery_level(self):
        if self.status:
            return self.status[1]
        return None

    @property
    def reboot_count(self):
        if self.status:
            return self.status[-1]
        return None

    @property
    def mode(self):
        if self.status:
            _mode = self.status[2]
            if _mode & 0x02:
                return 1
            if _mode & 0x10:
                return 2
            return 0
        return None

    @property
    def mode_name(self):
        return self.device_settings.mode_names[self.mode]

    def log_print(self, message, timestamp=True):

        if not self.log_stream:
            return

        ts_pattern = "[%m-%d-%y_%H-%M-%S] "
        if timestamp:
            self.log_stream.write(datetime.now().strftime(ts_pattern))
        if isinstance(message, list) and len(message):
            for i, s in enumerate(message):
                if i == 0:
                    self.log_stream.write(s + '\n')
                else:
                    self.log_stream.write(' '*len(ts_pattern) + s + '\n')
        else:
            self.log_stream.write(message+'\n')

        self.log_stream.flush()

    def connect(self):
        self.log_print("Connecting to MAC address {} .......".format(self.mac_address))
        with self.backend_lock:
            try:
                self.requester.connect(True)
                self.log_print("Connected to {}!".format(self.mac_address))
            except Exception, e:
                self.log_print("Failed to connect to {}\n {}\n".format(self.mac_address, str(e)))

    def disconnect(self):
        self.log_print("Disconnecting ....")

        with self.backend_lock:
            self.requester.disconnect()
        self.log_print("Disconnected from {}!".format(self.mac_address))

    def read_by_handle(self, handle):
        if not self.is_connected():
            return
        with self.backend_lock:
            try:
                ret = self.requester.read_by_handle(handle)
            except Exception, e:
                self.log_print("Failed to read from handle {}\n {}\n".format(handle, str(e)))
                self.stop()
                ret = None
        return ret

    def write_by_handle(self, handle, data):
        with self.backend_lock:
            try:
                self.requester.write_by_handle(handle, data)
            except Exception, e:
                self.log_print("Failed to write to handle {}\n {}\n".format(handle, str(e)))
                self.stop()

    def read_status(self):
        _status = self.read_by_handle(self.device_settings.status_handle)[0]
        _config = self.read_by_handle(self.device_settings.config_handle)[0]
        self.status = st.unpack(self.device_settings.status_pattern, _status)
        self.config = st.unpack(self.device_settings.config_pattern, _config)
        self.total_logs = self.status[0]
        self.sample_period = 10 * self.config[self.mode * 2 + 1]

    def print_status(self):
        status = ["Status of the Device {}:".format(self.mac_address)]
        status.append("Battery: {}%        Total Logs: {}      Reboots: {}".format(self.battery_level, self.total_logs, self.reboot_count))
        status.append("Device is running in {} mode with sampling rate: {} ms".format(self.mode_name, self.sample_period))
        self.log_print(status)

    def blink(self):
        if not self.is_connected():
            return
        packet = st.pack(self.device_settings.blink_pattern, 5, 4, 6, 1, 5)
        self.write_by_handle(self.device_settings.config_handle, packet)

    def wait_notification(self):
        if not self.is_connected():
            return
        if not self.total_logs > 0:
            self.log_print("No logs to download")
            return

        self.requester.max_logs = self.total_logs
        self.requester.print_step = self.requester.max_logs // 100
        log_bit = 1 if self.raw else 3
        packet = st.pack(self.device_settings.download_pattern, 6, log_bit)
        start_time = datetime.now()
        full_fname = self.fname + start_time.strftime("_%m-%d-%y_%H-%M-%S") + ('_%s.dat' % self.mac_address.replace(':', ''))
        self.log_print("Writing data to file: {}".format(full_fname))
        self.requester.file = open(full_fname, 'w+')
        self.requester.file.write("raw\n" if self.raw else "compressed\n")
        self.requester.file.write("start_time: " + str(start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.write_by_handle(self.device_settings.config_handle, packet)
        bar = ProgBar(100, width=70, stream=self.log_stream)
        try:
            while not self.requester.done and not self.stopped:
                if (datetime.now() - start_time).seconds > 30:
                    packet = st.pack(self.device_settings.download_pattern, 6, 0)
                    self.write_by_handle(self.device_settings.config_handle, packet)
                    _ = self.read_by_handle(self.device_settings.config_handle)[0]
                    packet = st.pack(self.device_settings.download_pattern, 6, log_bit)
                    start_time = datetime.now()
                    self.write_by_handle(self.device_settings.config_handle, packet)
                self.received.clear()
                self.received.wait()
                bar.update()
            if self.requester.done:
                self.log_print("Download Complete")
                while bar.cnt < bar.max_iter:
                    bar.update()
            else:
                self.log_print("Download Interrupted")
        except (KeyboardInterrupt, SystemExit):
            self.log_print("Download Interrupted")
        except:
            raise
        finally:
            self.received.clear()
            self.log_print("Stopping device from broadcasting ....")
            packet = st.pack(self.device_settings.download_pattern, 6, 0)
            self.write_by_handle(self.device_settings.config_handle, packet)
            self.log_print("Waiting for all notifications to get handled ....")
            time.sleep(2)
            self.log_print("Closing File ....")
            self.requester.file.close()
