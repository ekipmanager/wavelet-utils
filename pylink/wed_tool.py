import sys
import time
import re
import os
import argparse

from multiprocessing import Process, Lock, Event, Manager
from wed_settings import Commands

backend_lock = Lock()


def start_command(mac_address, command, lock, log_file=None, wake_up=None, stop_event=None):
    from devices import DeviceInterface
    if log_file:
        logger = open(log_file, 'a')
    else:
        logger = sys.stdout
    device = DeviceInterface(mac_address, command, lock, log_stream=logger, wake_up=wake_up, stop_event=stop_event)
    try:
        device.run()
    except KeyboardInterrupt:
        pass
    except:
        raise
    finally:
        if log_file:
            logger.close()


def main():
    description = "Wavelet Device Communication Module"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--blink', dest='blink', help="Blink the red LED of the device", action='store_true')
    parser.add_argument('--device', dest='dev_macs', help="MAC address of the device", nargs='+')
    parser.add_argument('--download', dest='download', help="Download device log", action='store_true')
    parser.add_argument('--file', dest='fname', help="Path and the basename of the file to save the raw data to")
    parser.add_argument('--list', dest='discover', help="List all devices.", action='store_true')
    parser.add_argument('--log', dest='log_dir', help="Directory to save log files to")
    parser.add_argument('--raw', dest='raw', help="Download log files instead of compressed ones", action='store_true')
    parser.add_argument('--start', dest='config', help="Start downloading all devices using a yaml config file")
    parser.add_argument('--status', dest='status', help="Print the status of the devices", action='store_true')
    parser.add_argument('--stdout', dest='stdout', help="Print to screen", action='store_true')

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
            command = Commands.BLINK
        elif options.download:
            command = Commands.DOWNLOAD
        elif options.status:
            command = Commands.STATUS
        else:
            parser.print_help()
            return

        if not options.fname:
            options.fname = "./data/WED_data"

        if not options.log_dir:
            options.log_dir = "./logs"

        p_list = []

        for idx, dev in enumerate(options.dev_macs):
            stop_event = Event()
            wake_up = Event()
            if command == Commands.DOWNLOAD and not options.stdout:
                log_file = os.path.join(options.log_dir, "log_%s.log" % dev.replace(':', ''))
            else:
                log_file = None
            kwargs = {'mac_address': dev,
                      'command': command,
                      'lock': backend_lock,
                      'log_file': log_file,
                      'wake_up': wake_up,
                      'stop_event': stop_event}
            p = Process(target=start_command, kwargs=kwargs)
            p_list.append((p, wake_up, stop_event))
        try:
            for p in p_list:
                p[0].start()
            for p in p_list:
                p[0].join()

        except (KeyboardInterrupt, SystemExit):
            print("\nCancelling downloads in %d seconds....\n" % 4*len(options.dev_macs))
            time.sleep(4 * len(options.dev_macs))
            for p in p_list:
                p[0].terminate()
            sys.exit(0)
        except:
            raise

if __name__ == '__main__':
    main()

