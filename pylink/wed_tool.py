from __future__ import print_function
import sys
import argparse
from datetime import datetime
import struct as st
from gattlib import *
from threading import Event

from cutils.sensors.converter import convert


class Requester(GATTRequester):
    def __init__(self, wakeup, *args):
        GATTRequester.__init__(self, *args)
        self.wakeup = wakeup
        self.log_count = 0
        self.done = False
        self.max_logs = 100
        self.file = None

    def on_notification(self, handle, data):
        if self.log_count > self.max_logs:
            if not self.done:
                self.done = True
        else:
            logs = convert(data[3:])
            self.log_count += len(logs)
            self.file.writelines([b.name + ": " + str(b)+'\n' for b in logs])
        self.wakeup.set()


class DeviceInterface(object):
    def __init__(self, address, download=False, fname=None):

        self.address = address
        self.fname = fname

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

        self.received = Event()
        self.requester = Requester(self.received, address, False)

        self.connect()
        self.read_status()
        if download:
            self.wait_notification()

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

    def connect(self):
        print("Connecting to MAC address {} ... ".format(self.address))
        sys.stdout.flush()
        self.requester.connect(True)
        print("Connected")

    def read_status(self):
        _status = self.requester.read_by_handle(self.status_handle)[0]
        _config = self.requester.read_by_handle(self.config_handle)[0]
        self.status = st.unpack(self.status_pattern, _status)
        self.config = st.unpack(self.config_pattern, _config)
        self.total_logs = self.status[0]
        self.sample_period = self.config[self.mode * 2 + 1]

    def blink(self):
        blink_pattern = "=BBBBB"
        packet = st.pack(blink_pattern, 5, 4, 6, 1, 5)
        self.requester.write_by_handle(self.config_handle, packet)

    def wait_notification(self):
        self.requester.max_logs = self.total_logs
        packet = st.pack(self.download_pattern, 6, 1)
        start_time = datetime.now()
        full_fname = self.fname + start_time.strftime("_%m-%d-%y_%H-%M-%S.log")
        self.requester.file = open(full_fname, 'w+')
        self.requester.file.write("start_time: " + str(start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.requester.write_by_handle(self.config_handle, packet)
        while not self.requester.done:
            if self.requester.log_count % 1000:
                sys.stdout.write("\rDownloaded %d logs out of %d " % (self.requester.log_count, self.total_logs))
                sys.stdout.flush()
                if (datetime.now() - start_time).seconds > 30:
                    packet = st.pack(self.download_pattern, 6, 0)
                    self.requester.write_by_handle(self.config_handle, packet)
                    _ = self.requester.read_by_handle(self.config_handle)[0]
                    packet = st.pack(self.download_pattern, 6, 1)
                    start_time = datetime.now()
                    self.requester.write_by_handle(self.config_handle, packet)
            self.received.clear()
            self.received.wait()
        print("\nDownload Complete")
        self.received.clear()
        packet = st.pack(self.download_pattern, 6, 0)
        self.requester.write_by_handle(self.config_handle, packet)
        self.requester.file.close()
        self.requester.disconnect()


def main():
    description = "Wavelet Device Communication Module"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--list", dest="discover", help="List all devices.", action="store_true")
    parser.add_argument("--device", dest="device_mac", help="MAC address of the device")
    parser.add_argument("--blink", dest="blink", help="Blink the red LED of the device", action="store_true")
    parser.add_argument("--download", dest="download", help="Download device log", action="store_true")
    parser.add_argument("--file", dest="fname", help="Path and the basename of the file to save the logs to")

    if len(sys.argv) == 1:
        parser.print_help()

    options = parser.parse_args()

    if options.discover:
        service = DiscoveryService()
        print("Discovering devices nearby...")
        sys.stdout.flush()
        devices = service.discover(2)
        if not len(devices):
            print("Looking more ...")
            devices = service.discover(5)
        if not len(devices):
            print("No device found")
            return
        print("{:<20} {:<20} ".format('MAX Address', 'Name'))
        for k, v in devices.items():
            print("{:<20} {:<20} ".format(k, v))
        return

    if options.blink:
        if not options.device_mac:
            raise RuntimeError("Blink requires the MAC address of the device")
        device = DeviceInterface(options.device_mac)
        device.blink()
        device.requester.disconnect()
        del device

    if options.download:
        if not options.fname:
            options.fname = "./WED_log"
        try:
            DeviceInterface(options.device_mac, download=True, fname=options.fname)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == '__main__':
    main()
