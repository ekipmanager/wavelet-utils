from __future__ import print_function
import sys
import time
import re
import os
import argparse
import signal
import yaml
from Queue import PriorityQueue

from datetime import datetime
from multiprocessing import Process, Lock, Event
from multiprocessing.managers import SyncManager
from wed_settings import Commands

backend_lock = Lock()


def start_command(mac_address, log_file=None, **kwargs):
    from devices import DeviceInterface
    if log_file:
        logger = open(log_file, 'a')
    else:
        logger = sys.stdout
    device = DeviceInterface(mac_address, log_stream=logger, **kwargs)
    device.run()
    if log_file:
        logger.close()


def sync_manager_init():
    # Make a manager that ignores keyboard interrupt
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def start_pool(config_file):
    manager = SyncManager()
    manager.start(sync_manager_init)
    status_dict = manager.dict()
    pr_queue = PriorityQueue()
    with open(config_file, 'r') as f:
        options = yaml.load(f)

    dev_macs = options.get('devices', None)
    if not dev_macs:
        print("No device found in the config file")
        return

    for dev_mac in dev_macs:
        if not is_mac_valid(dev_mac):
            raise ValueError("{} is not a valid MAC address!".format(dev_mac))
        pr_queue.put_nowait((0, dev_mac))
        status_dict[dev_mac] = 0

    battery_warn = options.get('battery_warn', 0) or 20
    log_dir = options.get('log_dir', 0) or './logs/'
    data_dir = options.get('data_dir', 0) or './data/'
    max_process = options.get('max_process', 0) or 3
    raw = options.get('raw', False)
    fname = os.path.join(data_dir, options.get('data_prefix', 'WED_data'))
    min_logs = options.get('min_logs', 1000)

    common_kwargs = {'command': Commands.DOWNLOAD,
                     'backend_lock': backend_lock,
                     'fname': fname,
                     'battery_warn': battery_warn,
                     'raw': raw,
                     'status_dict': status_dict,
                     'min_logs': min_logs,
                     }
    process_list = []
    max_process = min(max_process, len(dev_macs))
    retries = {d: 0 for d in dev_macs}

    def get_next_process():
        mac_address = pr_queue.get_nowait()[1]
        stop_event = Event()
        wake_up = Event()
        log_file = os.path.join(log_dir, "log_%s.log" % mac_address.replace(':', ''))
        kwargs = {'mac_address': mac_address,
                  'log_file': log_file,
                  'wake_up': wake_up,
                  'stop_event': stop_event,
                  }
        kwargs.update(common_kwargs)
        p = Process(target=start_command, kwargs=kwargs)
        return p, mac_address, status_dict[mac_address], wake_up, stop_event

    for i in range(max_process):
        process_list.append(get_next_process())

    for p in process_list:
        p[0].start()
    try:
        while len(process_list) > 0:
            p = process_list.pop(0)
            if p[0].is_alive():
                process_list.append(p)
            else:
                last_checked = status_dict[p[1]]
                if last_checked == p[2]:
                    retries[p[1]] += 1
                    if retries[p[1]] > 3:
                        last_checked = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
                        retries[p[1]] = 0
                else:
                    retries[p[1]] = 0
                pr_queue.put_nowait((last_checked, p[1]))
                new_process = get_next_process()
                new_process[0].start()
                process_list.append(new_process)
            time.sleep(2)

    except (KeyboardInterrupt, SystemExit):
        delay = 4 * len([p for p in process_list if p[0].is_alive()])
        print("\nCancelling downloads..............\nWaiting %d seconds for all devices to clean up....\n" % delay)
        time.sleep(delay)
        for p in process_list:
            p[0].terminate()
        sys.exit(0)
    except:
        raise


def is_mac_valid(mac_address):
    mac_format = "[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
    return re.match(mac_format, mac_address.lower())


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

    elif options.config:
        start_pool(options.config)
    elif options.dev_macs:
        # Check all the mac addresses to be valid
        for dev_mac in options.dev_macs:
            if not is_mac_valid(dev_mac):
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
            options.log_dir = "./logs/"

        process_list = []
        for idx, dev in enumerate(options.dev_macs):
            stop_event = Event()
            wake_up = Event()
            if command == Commands.DOWNLOAD and not options.stdout:
                log_file = os.path.join(options.log_dir, "log_%s.log" % dev.replace(':', ''))
            else:
                log_file = None
            kwargs = {'mac_address': dev,
                      'command': command,
                      'backend_lock': backend_lock,
                      'log_file': log_file,
                      'fname': options.fname,
                      'wake_up': wake_up,
                      'stop_event': stop_event,
                      }
            p = Process(target=start_command, kwargs=kwargs)
            process_list.append((p, wake_up, stop_event))

        for p in process_list:
            p[0].start()

        try:
            for p in process_list:
                p[0].join()

        except (KeyboardInterrupt, SystemExit):
            delay = 4 * len(options.dev_macs)
            print("\nCancelling downloads / Waiting %d seconds for all devices to clean up....\n" % delay)
            time.sleep(delay)
            for p in process_list:
                p[0].terminate()
            sys.exit(0)
        except:
            raise


if __name__ == '__main__':
    main()

