from __future__ import print_function
import sys, time
import argparse
from datetime import datetime
import struct as st
from gattlib import *
import threading

from cutils.sensors.converter import convert


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

    def on_notification(self, handle, data):
        # sys.stdout.write("Received Notification on handle %d\n" % handle)
        # sys.stdout.flush()
        if self.log_count > self.max_logs:
            if not self.done:
                sys.stdout.write("Done------------------------- %d\n" % self.log_count)
                sys.stdout.flush()
                self.done = True
                self.wakeup.set()
        logs = convert(data[3:])
        self.log_count += len(logs)
        self.file.writelines([b.name + ": " + str(b)+'\n' for b in logs])
        # sys.stdout.write("Wrote %d logs to file\n" % len(logs))
        # sys.stdout.flush()
        self.wakeup.set()


class DeviceInterface(threading.Thread):
    def __init__(self, address, command, fname=None):

        super(DeviceInterface, self).__init__()
        self.address = address
        self.fname = fname
        self.command = command

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
        self.sample_period = 10 * self.config[self.mode * 2 + 1]

    def blink(self):
        blink_pattern = "=BBBBB"
        packet = st.pack(blink_pattern, 5, 4, 6, 1, 5)
        self.requester.write_by_handle(self.config_handle, packet)

    def wait_notification(self):
        if not self.total_logs > 0:
            print("No logs to download")
            return

        # self.requester.max_logs = self.total_logs
        packet = st.pack(self.download_pattern, 6, 1)
        start_time = datetime.now()
        full_fname = self.fname + start_time.strftime("_%m-%d-%y_%H-%M-%S") + ('_%s.log' % self.address.replace(':', ''))
        self.requester.file = open(full_fname, 'w+')
        self.requester.file.write("start_time: " + str(start_time) + '\n')
        self.requester.file.write("sample_period: " + str(self.sample_period) + '\n')
        self.requester.write_by_handle(self.config_handle, packet)
        while not self.requester.done and not self.stopped:
            # if self.requester.log_count % 200 == 0:
            #     sys.stdout.write("\rDownloaded %d logs out of %d " % (self.requester.log_count, self.total_logs))
            #     sys.stdout.flush()
            #     if (datetime.now() - start_time).seconds > 30:
            #         packet = st.pack(self.download_pattern, 6, 0)
            #         self.requester.write_by_handle(self.config_handle, packet)
            #         _ = self.requester.read_by_handle(self.config_handle)[0]
            #         packet = st.pack(self.download_pattern, 6, 1)
            #         start_time = datetime.now()
            #         self.requester.write_by_handle(self.config_handle, packet)
            self.received.clear()
            # sys.stdout.write("Waiting .... \n")
            # sys.stdout.flush()
            self.received.wait()

        print("\nDownload Complete")
        self.received.clear()
        sys.stdout.write("Writing Shut UP .... \n")
        sys.stdout.flush()
        packet = st.pack(self.download_pattern, 6, 0)
        self.requester.write_by_handle(self.config_handle, packet)
        sys.stdout.write("Waiting for all notifications to get handled .... \n")
        sys.stdout.flush()
        time.sleep(2)
        sys.stdout.write("Closing File .... \n")
        sys.stdout.flush()
        self.requester.file.close()
        sys.stdout.write("Disconnecting .... \n")
        sys.stdout.flush()
        self.requester.disconnect()
        sys.stdout.write("Disconnected .... \n")
        sys.stdout.flush()


def main():
    description = "Wavelet Device Communication Module"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--list", dest="discover", help="List all devices.", action="store_true")
    parser.add_argument("--device", dest="dev_macs", help="MAC address of the device", nargs='+')
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

    elif options.dev_macs:
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
                                         fname=options.fname)
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

        except KeyboardInterrupt:
            print("Cancelling downloads ....")
            for device in devices:
                device.stop()
            sys.exit(0)

if __name__ == '__main__':
    main()
