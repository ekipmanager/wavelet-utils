from __future__ import print_function
import sys, time, re
import argparse
from datetime import datetime
import struct as st
from gattlib import *
import threading
from pyprind import ProgBar

from cutils.sensors.converter import convert, get_log_count


class Commands():
    STATUS = 0
    BLINK = 1
    DOWNLOAD = 2

printLock = threading.Lock()


def safe_print(message):
    with printLock:
        sys.stdout.write(message)
        sys.stdout.flush()


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
    def __init__(self, address, command, fname=None, raw=False):

        super(DeviceInterface, self).__init__()
        self.address = address
        self.fname = fname
        self.command = command
        self.raw = True

        self.daemon = True
        self._stop = threading.Event()

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
            self.requester.disconnect()

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
        safe_print("Connecting to MAC address {} .......\n".format(self.address))
        self.requester.connect(True)
        safe_print("Connected to {}!\n".format(self.address))

    def disconnect(self):
        self.requester.disconnect()

    def read_status(self):
        _status = self.requester.read_by_handle(self.status_handle)[0]
        _config = self.requester.read_by_handle(self.config_handle)[0]
        self.status = st.unpack(self.status_pattern, _status)
        self.config = st.unpack(self.config_pattern, _config)
        self.total_logs = self.status[0]
        self.sample_period = 10 * self.config[self.mode * 2 + 1]

    def blink(self):
        if not self.is_connected():
            return
        blink_pattern = "=BBBBB"
        packet = st.pack(blink_pattern, 5, 4, 6, 1, 5)
        self.requester.write_by_handle(self.config_handle, packet)

    def wait_notification(self):
        if not self.is_connected():
            return
        if not self.total_logs > 0:
            safe_print("No logs to download\n")
            return

        self.requester.max_logs = self.total_logs
        self.requester.print_step = self.total_logs // 100
        log_bit = 1 if self.raw else 3
        packet = st.pack(self.download_pattern, 6, log_bit)
        start_time = datetime.now()
        full_fname = self.fname + start_time.strftime("_%m-%d-%y_%H-%M-%S") + ('_%s.log' % self.address.replace(':', ''))
        self.requester.file = open(full_fname, 'w+')
        self.requester.file.write("raw\n" if self.raw else "compressed\n")
        self.requester.file.write("start_time: " + str(start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.requester.write_by_handle(self.config_handle, packet)
        bar = ProgBar(100, width=70)
        while not self.requester.done and not self.stopped:
            # safe_print("\rDownloaded %d logs out of %d " % (self.requester.log_count, self.total_logs))
            if (datetime.now() - start_time).seconds > 45:
                packet = st.pack(self.download_pattern, 6, 0)
                self.requester.write_by_handle(self.config_handle, packet)
                _ = self.requester.read_by_handle(self.config_handle)[0]
                packet = st.pack(self.download_pattern, 6, log_bit)
                start_time = datetime.now()
                self.requester.write_by_handle(self.config_handle, packet)
            self.received.clear()
            self.received.wait()
            bar.update()
        while bar.cnt < bar.max_iter:
            bar.update()
        safe_print("\rDownloaded %d logs out of %d" % (self.requester.log_count, self.total_logs))
        if self.requester.done:
            safe_print("\nDownload Complete\n")
        else:
            safe_print("\nDownload Interrupted\n")
        self.received.clear()
        safe_print("Stopping device from broadcasting ....\n")
        packet = st.pack(self.download_pattern, 6, 0)
        self.requester.write_by_handle(self.config_handle, packet)
        safe_print("Waiting for all notifications to get handled ....\n")
        time.sleep(2)
        safe_print("Closing File ....\n")
        self.requester.file.close()
        safe_print("Disconnecting ....\n")
        self.requester.disconnect()
        safe_print("Disconnected ....\n")


def main():
    description = "Wavelet Device Communication Module"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--list", dest="discover", help="List all devices.", action="store_true")
    parser.add_argument("--device", dest="dev_macs", help="MAC address of the device", nargs='+')
    parser.add_argument("--blink", dest="blink", help="Blink the red LED of the device", action="store_true")
    parser.add_argument("--download", dest="download", help="Download device log", action="store_true")
    parser.add_argument("--file", dest="fname", help="Path and the basename of the file to save the logs to")
    parser.add_argument("--raw", dest="raw", help="Download log files instead of compressed ones", action="store_true")

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

    elif options.dev_macs:
        # Check all the mac addresses to be valid
        mac_format = "[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
        for dev_mac in options.dev_macs:
            if not re.match(mac_format, dev_mac.lower()):
                raise ValueError("{} is not a valid MAC address!".format(dev_mac))
        devices = []
        if options.blink:
            command = Commands.BLINK
        elif options.download:
            command = Commands.DOWNLOAD
        else:
            parser.print_help()
            return

        if not options.fname:
            options.fname = "./WED_log"

        try:
            for dev_mac in options.dev_macs:
                device = DeviceInterface(dev_mac,
                                         command=command,
                                         fname=options.fname,
                                         raw=options.raw)
                devices.append(device)
            for device in devices:
                try:
                    device.connect()
                    device.read_status()
                except Exception, e:
                    print("Error connecting to MAC address %s" % device.address)
                    print(e.args[0])
                    continue
            for device in devices:
                device.start()

            for device in devices:
                device.join()

        except (KeyboardInterrupt, SystemExit):
            safe_print("Cancelling downloads ....\n")
            for device in devices:
                device.stop()
            time.sleep(1 * len(devices))
            sys.exit(0)

if __name__ == '__main__':
    main()

