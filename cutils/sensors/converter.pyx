
from c_converter cimport *
import numpy as np
cimport numpy as np
cimport cython


# intentionally do not add __cinit__ to reduce overhead

FLAG_FAST = 0x01
FLAG_SLEEP = 0x02
FLAG_DEBUG = 0x10
FLAG_REBOOT = 0x80

cdef class TimestampSensorLog:
    cdef public:
        uint32_t timestamp
        uint8_t flags

    def __reduce__(self):
        return rebuild_timestamp_log, (self.timestamp, self.flags)

    def __repr__(self):
        meta = {
            'seconds': self.seconds,
            'ticks': self.ticks,
        }
        if self.passive:
            meta['passive'] = True
        if self.fast_rate:
            meta['fast_rate'] = True
        if self.sleep:
            meta['sleep'] = True
        if self.debug:
            meta['debug'] = True
            meta['errcode'] = self.errcode
        if self.reboot:
            meta['reboot'] = True
        return unicode(meta)

    property name:
        def __get__(self):
            if self.debug:
                return u'debug'
            return u'timestamp'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'timestamp'

    property ticks:
        def __get__(self):
            return self.timestamp

    property seconds:
        def __get__(self):
            return float(self.timestamp) / 128.0

    property debug:
        def __get__(self):
            return bool(self.flags & FLAG_DEBUG)

    property errcode:
        def __get__(self):
            return self.timestamp

    property sleep:
        def __get__(self):
            return bool(self.flags & FLAG_SLEEP)

    property fast_rate:
        def __get__(self):
            return bool(self.flags & FLAG_FAST)

    property passive:
        def __get__(self):
            return not (self.fast_rate or self.sleep)

    property reboot:
        def __get__(self):
            return bool(self.flags & FLAG_REBOOT)

def rebuild_timestamp_log(timestamp, flags):
    p = TimestampSensorLog()
    p.timestamp = timestamp
    p.flags = flags
    return p

cdef class AccelerometerSensorLog:
    cdef public:
        int8_t x
        int8_t y
        int8_t z

    def __reduce__(self):
        return rebuild_accelerometer_log, (self.x, self.y, self.z)

    def __repr__(self):
        return unicode([self.x, self.y, self.z])

    property name:
        def __get__(self):
            return u'accelerometer'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'accelerometer'

def rebuild_accelerometer_log(x, y, z):
    p = AccelerometerSensorLog()
    p.x = x
    p.y = y
    p.z = z
    return p

cdef class AccelerometerCompressedSensorLog:
    cdef public:
        uint8_t count_bits
        object data

    def __cinit__(self):
        self.data = []

    def __reduce__(self):
        return rebuild_accelerometer_compressed_log, (self.count_bits, self.data)

    def __repr__(self):
        meta = {}
        meta['count_bits'] = self.count_bits
        meta['data'] = self.data
        return unicode(meta)

    property name:
        def __get__(self):
            return u'accelerometer_compressed'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'accelerometer_compressed'

def rebuild_accelerometer_compressed_log(count_bits, data):
    p = AccelerometerCompressedSensorLog()
    p.count_bits = count_bits
    p.data = data
    return p

cdef class LightSensorConfigLog:
    cdef public:
        uint8_t dac_on
        uint8_t flags
        uint8_t level_led
        uint8_t gain
        uint8_t log_size

    def __reduce__(self):
        return rebuild_lightsensor_config_log, (
            self.dac_on, self.flags, self.level_led, self.gain, self.log_size
        )

    def __repr__(self):
        return unicode(self.config)

    property name:
        def __get__(self):
            return u'lightsensor_config'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'lightsensor_config'

    property config:
        def __get__(self):
            return {
                'dac_on': self.dac_on,
                'flags': self.flags,
                'level_led': self.level_led,
                'gain': self.gain,
                'log_size': self.log_size,
            }

def rebuild_lightsensor_config_log(dac_on, flags, level_led, gain, log_size):
    p = LightSensorConfigLog()
    p.dac_on = dac_on
    p.flags = flags
    p.level_led = level_led
    p.gain = gain
    p.log_size = log_size
    return p

cdef class LightSensorLog:
    cdef public:
        uint16_t red
        uint16_t ir
        uint16_t off
        uint8_t flags

    def __reduce__(self):
        return rebuild_lightsensor_log, (self.red, self.ir, self.off, self.flags)

    def __repr__(self):
        return unicode(self.config)

    property name:
        def __get__(self):
            return u'lightsensor'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'lightsensor'

    property config:
        def __get__(self):
            meta = {}
            if self.flags & 1:
                meta['red'] = self.red
            if self.flags & 2:
                meta['ir'] = self.ir
            if self.flags & 4:
                meta['off'] = self.off
            return meta

def rebuild_lightsensor_log(red, ir, off, flags):
    p = LightSensorLog()
    p.red = red
    p.ir = ir
    p.off = off
    p.flags = flags
    return p

cdef class TemperatureSensorLog:
    cdef public:
        int16_t temperature

    def __reduce__(self):
        return rebuild_temperature_log, (self.temperature,)

    def __repr__(self):
        return unicode(self.config)

    property name:
        def __get__(self):
            return u'temperature'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'temperature'

    property celsius:
        def __get__(self):
            celsius = float(self.temperature) / 10.0
            return celsius

    property fahrenheit:
        def __get__(self):
            celsius = self.celsius
            return (celsius * 1.8) + 32

    property config:
        def __get__(self):
            meta = {
                'celsius': self.celsius,
                'fahrenheit': self.fahrenheit,
            }
            return meta

def rebuild_temperature_log(temperature):
    p = TemperatureSensorLog()
    p.temperature = temperature
    return p

cdef class TagLog:
    cdef public:
        uint32_t tag

    def __reduce__(self):
        return rebuild_tag_log, (self.tag,)

    def __repr__(self):
        return unicode([self.tag])

    property name:
        def __get__(self):
            return u'tag'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'tag'

def rebuild_tag_log(tag):
    p = TagLog()
    p.tag = tag
    return p

cdef class LogCount:
    cdef public:
        uint32_t log_timestamp
        uint16_t log_accel_count
        uint32_t old_timestamp
        uint32_t timestamp

    def __reduce__(self):
        return rebuild_log_count_log, (
            self.log_timestamp, self.log_accel_count,
            self.old_timestamp, self.timestamp
        )

    def __repr__(self):
        return unicode(self.config)

    property name:
        def __get__(self):
            return u'log_count'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'log_count'

    property config:
        def __get__(self):
            meta = {
                'log_timestamp': self.log_timestamp,
                'log_accel_count': self.log_accel_count,
                'old_timestamp': self.old_timestamp,
                'timestamp': self.timestamp,
            }
            return meta

def rebuild_log_count_log(log_timestamp, log_accel_count,
                          old_timestamp, timestamp):
    p = LogCount()
    p.log_timestamp = log_timestamp
    p.log_accel_count = log_accel_count
    p.old_timestamp = old_timestamp
    p.timestamp = timestamp
    return p

cdef class EventLog:
    cdef public:
        uint8_t flags

    def __reduce__(self):
        return rebuild_event_log, (self.flags,)

    def __repr__(self):
        return {
            'flags': self.flags
        }

    property name:
        def __get__(self):
            return u'event'

    property FRIENDLY_NAME:
        def __get__(self):
            return u'event'

def rebuild_event_log(flags):
    p = EventLog()
    p.flags = flags
    return p

cdef get_packet(const char * log):
    pk_type = log[0] & WED_TAG_BITS

    cdef WEDLogTimestamp *p_ts
    if pk_type == WED_LOG_TIME:
        p_ts = <WEDLogTimestamp *>&log[0]
        pkt = TimestampSensorLog()
        pkt.timestamp = p_ts.timestamp
        pkt.flags = p_ts.flags
        return pkt

    cdef WEDLogAccel *p_accel
    if pk_type == WED_LOG_ACCEL:
        p_accel = <WEDLogAccel *>&log[0]
        pkt = AccelerometerSensorLog()
        pkt.x = p_accel.accel[0]
        pkt.y = p_accel.accel[1]
        pkt.z = p_accel.accel[2]
        return pkt

    cdef WEDLogAccelCmp *p_accel_cmp
    if pk_type == WED_LOG_ACCEL_CMP:
        p_accel_cmp = <WEDLogAccelCmp *>&log[0]
        pkt = AccelerometerCompressedSensorLog()
        pkt.count_bits = p_accel_cmp.count_bits
        packet_len = get_packet_len(<const char *>&log[0])
        for ii in range(packet_len - 2):
            pkt.data.append(log[ii + 2])
        return pkt

    cdef WEDLogLSConfig *p_ls_conf
    if pk_type == WED_LOG_LS_CONFIG:
        p_ls_conf = <WEDLogLSConfig *>&log[0]
        pkt = LightSensorConfigLog()
        pkt.dac_on = p_ls_conf.dac_on
        pkt.flags = p_ls_conf.flags
        pkt.level_led = p_ls_conf.level_led
        pkt.gain = p_ls_conf.gain
        pkt.log_size = p_ls_conf.log_size
        return pkt

    cdef WEDLogLSData *p_ls
    if pk_type == WED_LOG_LS_DATA:
        p_ls = <WEDLogLSData *>&log[0]
        pkt = LightSensorLog()
        pkt.flags = (log[0] & 0xE0) >> 5
        if pkt.flags & 1:
            pkt.red = p_ls.val[0]
        if pkt.flags & 2:
            pkt.ir = p_ls.val[1]
        if pkt.flags & 4:
            pkt.off = p_ls.val[2]
        return pkt

    cdef WEDLogTemp *p_temp
    if pk_type == WED_LOG_TEMP:
        p_temp = <WEDLogTemp *>&log[0]
        pkt = TemperatureSensorLog()
        pkt.temperature = p_temp.temperature
        return pkt

    cdef uint32_t tag
    cdef WEDLogTag *p_tag
    if pk_type == WED_LOG_TAG:
        p_tag = <WEDLogTag *>&log[0]
        pkt = TagLog()
        tag = (
            p_tag.tag[0] |
            ( <uint32_t>p_tag.tag[1] << 8 ) |
            ( <uint32_t>p_tag.tag[2] << 16 ) |
            ( <uint32_t>p_tag.tag[3] << 24 )
        )
        pkt.tag = tag
        return pkt

    cdef WEDLogCount * p_cnt
    if pk_type == WED_LOG_COUNT:
        p_cnt = <WEDLogCount *>&log[0]
        pkt = LogCount()
        pkt.log_timestamp = p_cnt.log_timestamp
        pkt.log_accel_count = p_cnt.log_accel_count
        pkt.old_timestamp = p_cnt.old_timestamp
        pkt.timestamp = p_cnt.timestamp
        return pkt

    cdef WEDLogEvent * p_ev
    if pk_type == WED_LOG_COUNT:
        p_ev = <WEDLogEvent *>&log[0]
        pkt = EventLog()
        pkt.flags = p_ev.flags
        return pkt

    raise ValueError('Unknown packet of type %d' % pk_type)

@cython.boundscheck(False)
@cython.wraparound(False)
def convert(logs_str not None, ignore_unknown=True):
    """
    Separate stream into chunks
    :param logs_str:      byte stream of logs (uncompressed)
    :return:              list of Python objects for logs
    """
    converted = []
    if not logs_str:
        return converted

    data_len = len(logs_str)
    if data_len < 2:
        return converted

    cdef char* logs = logs_str

    cdef int count = 0

    while count < data_len:
        packet_len = get_packet_len(<const char *>&logs[count])
        if count + packet_len > data_len:
            break
        pk_type = logs[count] & WED_TAG_BITS
        if ignore_unknown and (pk_type < 0 or pk_type > WED_LOG_EVENT):
            break
        converted.append(get_packet(<const char *>&logs[count]))
        count = count + packet_len
    return converted

@cython.boundscheck(False)
@cython.wraparound(False)
def get_log_count(logs_str not None, ignore_unknown=True):
    """
    Return number of logs in a log stream
    :param logs_str:      byte stream of logs (compressed or uncompressed)
    :return:              number of logs in the byte stream
    """

    if not logs_str:
        return 0

    data_len = len(logs_str)
    if data_len < 2:
        return 0

    cdef char* logs = logs_str

    cdef int count = 0
    cdef int total_logs = 0

    while count < data_len:
        packet_len = get_packet_len(<const char *>&logs[count])
        if count + packet_len > data_len:
            break
        pk_type = logs[count] & WED_TAG_BITS
        if ignore_unknown and (pk_type < 0 or pk_type > WED_LOG_EVENT):
            break
        if pk_type == WED_LOG_ACCEL_CMP:
            total_logs += get_compressed_log_count(<const char *>&logs[count])
        else:
            total_logs += 1
        count = count + packet_len
    return total_logs

@cython.boundscheck(False)
@cython.wraparound(False)
def decompress_stream(logs not None):
    '''Decompress stream
    Inputs:
        logs - byte stream of logs (potentially compressed)
    Outputs:
        outBuf - decompressed byte array
    '''

    cdef np.uint8_t[:] inBuf
    inBuf = np.ascontiguousarray(logs, dtype=np.uint8)

    cdef int res
    cdef int nInLen = len(inBuf)
    cdef int nOutLen
    cdef cmp_state_t state
    state.accel.bValid = 0
    state.ignored_cmp_count = 0
    res = stream_len(<const char *>&inBuf[0], &nInLen, &nOutLen, &state)
    # In case of invalid packet, go ahead and decompress valid ones
    if res < 0 and res != AMERR_UNPROCESED_INPUT:
        raise RuntimeError("Invalid stream (%d)" % res)
    if nInLen == 0:
        raise RuntimeError("Empty input stream")
    cdef np.uint8_t[:] outBuf = np.zeros(nOutLen, dtype=np.uint8)
    if nOutLen > 0:
        res = stream_decompress(<const char *>&inBuf[0], &nInLen, <char *>&outBuf[0], &nOutLen, &state)
        if res < 0:
            raise RuntimeError("Decompression error or invalid packet (%d)" % res)

    return np.asarray(outBuf), nInLen, state.ignored_cmp_count