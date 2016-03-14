from __future__ import print_function
import pandas as pd
from dateutil.parser import parse as datetime_parser
import datetime


def stamp_log_file(fname):
    with open(fname, 'r') as f:
        lines = f.readlines()

    if not lines[0].startswith('start_time'):
        raise NotImplementedError("The time-stamping does not support this type of file")

    start_time = datetime_parser(lines[0][12:-1])
    sampling_period = int(lines[1][15:-1])
    accel_logs = [l[16:-2].split(',') for l in lines[2:] if l.startswith('accel')]
    time_stamps = [start_time - datetime.timedelta(milliseconds=sampling_period * i) for i in range(len(accel_logs))][::-1]

    return pd.DataFrame(accel_logs, index=pd.DatetimeIndex(time_stamps), columns=['Ax', 'Ay', 'Az'], dtype=int)
