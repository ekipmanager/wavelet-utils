import sys, time, re, os
import argparse

from multiprocessing import Process, Lock, Event

backend_lock = Lock()


def start_device(address, command, lock, log_file=None, stop_event=None):
    from devices import DeviceInterface, Commands
    if command == 'download':
        dev_command = Commands.DOWNLOAD
    else:
        dev_command = Commands.BLINK
    logger = open(log_file, 'w+')
    device = DeviceInterface(address, dev_command, lock, log_stream=logger, stop_event=stop_event)
    device.connect()
    device.read_status()
    device.start()
    device.join()
    logger.close()


def main():
    description = "Wavelet Device Communication Module"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--list", dest="discover", help="List all devices.", action="store_true")
    parser.add_argument("--device", dest="dev_macs", help="MAC address of the device", nargs='+')
    parser.add_argument("--blink", dest="blink", help="Blink the red LED of the device", action="store_true")
    parser.add_argument("--download", dest="download", help="Download device log", action="store_true")
    parser.add_argument("--file", dest="fname", help="Path and the basename of the file to save the logs to")
    parser.add_argument("--log", dest="log_dir", help="Directory to save log files to")
    parser.add_argument("--raw", dest="raw", help="Download log files instead of compressed ones", action="store_true")

    if len(sys.argv) == 1:
        parser.print_help()

    options = parser.parse_args()

    if options.discover:
        from gattlib import DiscoveryService
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
        if options.blink:
            command = 'blink'
        elif options.download:
            command = 'download'
        else:
            parser.print_help()
            return

        if not options.fname:
            options.fname = "./WED_data"

        if not options.log_dir:
            options.log_dir = "./"

        try:
            p_list = []
            for idx, dev in enumerate(options.dev_macs):
                stop_event = Event()
                log_file = os.path.join(options.log_dir, "log_%s.log" % dev.replace(':', ''))
                p = Process(target=start_device, args=(dev, command, backend_lock, log_file, stop_event))
                p_list.append((p, stop_event))

            for p in p_list:
                p[0].start()
            for p in p_list:
                p[0].join()

        except (KeyboardInterrupt, SystemExit):
            print("Cancelling downloads in %d seconds....\n" % 2*len(options.dev_macs))
            for p in p_list:
                p[1].set()

            time.sleep(2 * len(options.dev_macs))
            for p in p_list:
                p[0].terminate()
            sys.exit(0)

if __name__ == '__main__':
    main()

