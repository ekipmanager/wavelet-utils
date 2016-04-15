from __future__ import print_function
import pandas as pd
from dateutil.parser import parse as datetime_parser
import datetime
from cutils.sensors.converter import decompress_stream, convert


def stamp_log_file(fname):
    with open(fname, 'r') as f:
        lines = f.readlines()

    if lines[0][:-1] == 'compressed':
        compressed = True
    elif lines[0][:-1] == 'raw':
        compressed = False
    else:
        raise NotImplementedError("The time-stamping does not support this type of file")

    start_time = datetime_parser(lines[1][12:-1])
    sampling_period = int(lines[2][15:-1])

    log_bytes = ''.join(lines[3:])
    if compressed:
        decomp_bytes = decompress_stream(bytearray(log_bytes))[0].tobytes()
        logs = convert(decomp_bytes)
    else:
        logs = convert(log_bytes)
    accel_logs = [[l.x, l.y, l.z] for l in logs if l.name.startswith('accel')]
    time_stamps = [start_time - datetime.timedelta(milliseconds=sampling_period * i) for i in range(len(accel_logs))][::-1]

    return pd.DataFrame(accel_logs, index=pd.DatetimeIndex(time_stamps), columns=['Ax', 'Ay', 'Az'], dtype=int)


def get_accel_counts(fname):
    with open(fname, 'r') as f:
        lines = f.readlines()

    if lines[0][:-1] == 'compressed':
        compressed = True
    elif lines[0][:-1] == 'raw':
        compressed = False
    else:
        raise NotImplementedError("The time-stamping does not support this type of file")

    log_bytes = ''.join(lines[3:])
    if compressed:
        decomp_bytes = decompress_stream(bytearray(log_bytes))[0].tobytes()
        logs = convert(decomp_bytes)
    else:
        logs = convert(log_bytes)
    return len([l for l in logs if l.name.startswith('accel')])
