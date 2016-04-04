from __future__ import print_function
import sys
import time
from datetime import datetime
import struct as st
from gattlib import *
import threading
from pyprind import ProgBar

from cutils.sensors.converter import get_log_count


class Commands():
    STATUS = 0
    BLINK = 1
    DOWNLOAD = 2


class Requester(GATTRequester):
    def __init__(self, wakeup, *args):
        GATTRequester.__init__(self, *args)
        self.wakeup = wakeup
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
                self.wakeup.set()
        self.file.write(data[3:])
        if self.log_count > self.next_print:
            self.next_print += self.print_step
            self.wakeup.set()


class DeviceInterface(threading.Thread):
    def __init__(self, address, command, backend_lock,
                 log_stream=None,
                 fname=None,
                 raw=False,
                 stop_event=None):

        super(DeviceInterface, self).__init__()
        self.address = address
        self.fname = fname
        if self.fname is None:
            self.fname = "./WED_data"
        self.command = command
        self.raw = raw
        self.backend_lock = backend_lock
        # TODO: Use logging
        if log_stream is None:
            self.log_stream = sys.stdout
        else:
            if not (hasattr(log_stream, 'write') and hasattr(log_stream, 'flush')):
                raise ValueError("No Valid stream found")
            self.log_stream = log_stream

        self.daemon = True
        self._stop = stop_event

        # BLE handles
        self.status_handle = 0x0025
        self.config_handle = 0x0027

        # packet formats
        self.download_pattern = '=BB'
        self.status_pattern = '=IBBIBBBBB'
        self.config_pattern = '=HHHHHHHBBB'

        # Initialize configs
        self.status = None
        self.total_logs = 0
        self.config = None
        self.sample_period = None
        self.mode_names = {0: "Slow Mode",
                           1: "Fast Mode",
                           2: "Sleep Mode"}

        self.received = threading.Event()
        self.requester = Requester(self.received, address, False)

    def stop(self):
        self._stop.set()

    @property
    def stopped(self):
        return self._stop.is_set()

    def is_connected(self):
        return self.requester.is_connected()

    def run(self):
        if self.command == Commands.DOWNLOAD:
            self.wait_notification()
        elif self.command == Commands.BLINK:
            self.blink()
            self.disconnect()

    @property
    def battery_level(self):
        if self.status:
            return self.status[1]
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

    def log_print(self, message, timestamp=True):
        if timestamp:
            message = datetime.now().strftime("[%m-%d-%y_%H-%M-%S]: ") + message + "\n"
        self.log_stream.write(message)
        self.log_stream.flush()

    def connect(self):
        self.log_print("Connecting to MAC address {} .......".format(self.address))
        with self.backend_lock:
            try:
                self.requester.connect(True)
                self.log_print("Connected to {}!".format(self.address))
            except Exception, e:
                self.log_print("Failed to connect to {}\n {}\n".format(self.address, str(e)))

    def disconnect(self):
        with self.backend_lock:
            self.requester.disconnect()
        self.log_print("Disconnected from {}!".format(self.address))

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
        _status = self.read_by_handle(self.status_handle)[0]
        _config = self.read_by_handle(self.config_handle)[0]
        self.status = st.unpack(self.status_pattern, _status)
        self.config = st.unpack(self.config_pattern, _config)
        self.total_logs = self.status[0]
        self.sample_period = 10 * self.config[self.mode * 2 + 1]

    def blink(self):
        if not self.is_connected():
            return
        blink_pattern = "=BBBBB"
        packet = st.pack(blink_pattern, 5, 4, 6, 1, 5)
        self.write_by_handle(self.config_handle, packet)

    def wait_notification(self):
        if not self.is_connected():
            return
        if not self.total_logs > 0:
            self.log_print("No logs to download")
            return

        self.requester.max_logs = self.total_logs
        self.requester.print_step = self.requester.max_logs // 100
        log_bit = 1 if self.raw else 3
        packet = st.pack(self.download_pattern, 6, log_bit)
        start_time = datetime.now()
        full_fname = self.fname + start_time.strftime("_%m-%d-%y_%H-%M-%S") + ('_%s.dat' % self.address.replace(':', ''))
        self.log_print("Writing data to file: {}".format(full_fname))
        self.requester.file = open(full_fname, 'w+')
        self.requester.file.write("raw\n" if self.raw else "compressed\n")
        self.requester.file.write("start_time: " + str(start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.write_by_handle(self.config_handle, packet)
        bar = ProgBar(100, width=70, stream=self.log_stream)
        while not self.requester.done and not self.stopped:
            if (datetime.now() - start_time).seconds > 30:
                packet = st.pack(self.download_pattern, 6, 0)
                self.write_by_handle(self.config_handle, packet)
                _ = self.read_by_handle(self.config_handle)[0]
                packet = st.pack(self.download_pattern, 6, log_bit)
                start_time = datetime.now()
                self.write_by_handle(self.config_handle, packet)
            self.received.clear()
            self.received.wait()
            bar.update()
        while bar.cnt < bar.max_iter:
            bar.update()
        if self.requester.done:
            self.log_print("Download Complete")
        else:
            self.log_print("Download Interrupted")
        self.received.clear()
        self.log_print("Stopping device from broadcasting ....")
        packet = st.pack(self.download_pattern, 6, 0)
        self.write_by_handle(self.config_handle, packet)
        self.log_print("Waiting for all notifications to get handled ....")
        time.sleep(2)
        self.log_print("Closing File ....")
        self.requester.file.close()
        self.log_print("Disconnecting ....")
        self.disconnect()
