import sys
import time
from datetime import datetime
import struct as st
from gattlib import *
from pyprind import ProgBar
from threading import Event

from cutils.sensors.converter import get_log_count
from wed_settings import *
from parsers.log_parse import get_accel_counts


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
                 stop_event=None,
                 battery_warn=20,
                 status_dict=None,
                 min_logs=1000):

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
        self.battery_warn = battery_warn

        if device_settings is None:
            self.device_settings = AmiigoSettings()
        else:
            self.device_settings = device_settings
        self.status_dict = status_dict

        # Initialize configs
        self.status = None
        self.start_time = None
        self.full_fname = None
        self.total_logs = 0
        self.min_logs = min_logs
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

    def stop(self):
        self._stop.set()

    def is_connected(self):
        return self.requester.is_connected()

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
            self.requester.connect(True)
            self.log_print("Connected to {}!".format(self.mac_address))

    def disconnect(self):
        self.log_print("Disconnecting from device {} .....".format(self.mac_address))
        if not self.is_connected():
            self.log_print("Device {} is already disconnected".format(self.mac_address))
            return
        with self.backend_lock:
            self.requester.disconnect()
        self.log_print("Disconnected from device {}!".format(self.mac_address))

    def read_by_handle(self, handle):
        with self.backend_lock:
            ret = self.requester.read_by_handle(handle)
        return ret

    def write_by_handle(self, handle, data):
        with self.backend_lock:
            self.requester.write_by_handle(handle, data)

    def read_status(self, update=False):
        _status = self.read_by_handle(self.device_settings.status_handle)[0]
        self.status = st.unpack(self.device_settings.status_pattern, _status)
        if not update:
            _config = self.read_by_handle(self.device_settings.config_handle)[0]
            self.config = st.unpack(self.device_settings.config_pattern, _config)
            self.total_logs = self.status[0]
            self.sample_period = 10 * self.config[self.mode * 2 + 1]

    def print_status(self):
        status = ["Status of the Device {}:".format(self.mac_address),
                  "Battery: {}%      Total Logs: {}      Reboots: {}".format(self.battery_level, self.status[0], self.reboot_count),
                  "Device is running in {} mode with sampling rate: {} ms".format(self.mode_name, self.sample_period),
                  ]
        if self.battery_level < self.battery_warn:
            status.append("****WARNING: Device {} battery is less than {}".format(self.battery_level, self.battery_warn))
        self.log_print(status)

    def blink(self):
        if not self.is_connected():
            return
        packet = st.pack(self.device_settings.blink_pattern, 5, 4, 6, 1, 5)
        self.write_by_handle(self.device_settings.config_handle, packet)

    def start_broadcast(self):
        log_bit = 1 if self.raw else 3
        packet = st.pack(self.device_settings.download_pattern, 6, log_bit)
        self.write_by_handle(self.device_settings.config_handle, packet)

    def stop_broadcast(self):
        packet = st.pack(self.device_settings.download_pattern, 6, 0)
        self.write_by_handle(self.device_settings.config_handle, packet)

    def download_data(self):
        if not self.is_connected():
            return
        if self.total_logs < self.min_logs:
            self.log_print("Not enough logs to start download, {} logs found but minimum logs is set to {}".
                           format(self.total_logs, self.min_logs))
            return

        self.requester.max_logs = self.total_logs
        self.requester.print_step = self.requester.max_logs // 100
        self.start_time = datetime.now()
        self.full_fname = self.fname + self.start_time.strftime("_%m-%d-%y_%H-%M-%S") + ('_%s.dat' % self.mac_address.replace(':', ''))
        self.log_print("Writing data to file: {}".format(self.full_fname))
        self.requester.file = open(self.full_fname, 'w+')
        self.requester.file.write("raw\n" if self.raw else "compressed\n")
        self.requester.file.write("start_time: " + str(self.start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.start_broadcast()
        bar = ProgBar(100, width=70, stream=self.log_stream)
        last_check = self.start_time
        timed_out = False
        try:
            while not timed_out and not self.requester.done and not self.stopped:
                if (datetime.now() - last_check).seconds > 30:
                    self.stop_broadcast()
                    self.read_status(update=True)
                    self.print_status()
                    last_check = datetime.now()
                    self.start_broadcast()
                self.received.clear()
                timed_out = not self.received.wait(30)
                bar.update()
            if self.requester.done:
                while bar.cnt < bar.max_iter:
                    bar.update()
                self.log_print("Download Complete")
            else:
                self.log_print("")
                self.log_print("Download Interrupted")

        except (KeyboardInterrupt, SystemExit):
            self.log_print("")
            self.log_print("Download Interrupted")

        finally:
            self.received.clear()
            if not timed_out:
                self.log_print("Stopping device from broadcasting ....")
                self.stop_broadcast()
                self.log_print("Waiting for all notifications to get handled ....")
                time.sleep(2)
            self.log_print("Closing File ....")
            self.requester.file.close()

    def run(self):
        try:
            self.connect()
            self.read_status()
            if self.command == Commands.DOWNLOAD:
                self.download_data()
            elif self.command == Commands.BLINK:
                self.blink()
            elif self.command == Commands.STATUS:
                self.print_status()
            self.disconnect()
        except Exception, e:
            self.log_print("Error encountered while running device {}\n {}\n".format(self.mac_address, str(e)))
        finally:
            if self.status_dict is not None and self.command == Commands.DOWNLOAD:
                if self.requester.log_count > 0:
                    epoch_time = (self.start_time - datetime(1970, 1, 1)).total_seconds()
                    if not self.requester.done:
                        epoch_time -= (self.total_logs - get_accel_counts(self.full_fname)) * self.sample_period / 1000
                    self.status_dict[self.mac_address] = int(epoch_time)
                elif self.total_logs < self.min_logs:
                    epoch_time = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
                    self.status_dict[self.mac_address] = int(epoch_time)

