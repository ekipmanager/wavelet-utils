
from libc.stdint cimport uint8_t, uint32_t, int8_t, uint16_t, int16_t

cdef extern from "cmodules/sensor_parse.h":

    ctypedef enum WED_LOG_TYPE:
        WED_LOG_TIME        = 0
        WED_LOG_ACCEL       = 1
        WED_LOG_LS_CONFIG   = 2
        WED_LOG_LS_DATA     = 3
        WED_LOG_TEMP        = 4
        WED_LOG_TAG         = 5
        WED_LOG_ACCEL_CMP   = 6
        WED_LOG_COUNT       = 7
        WED_LOG_EVENT       = 8

    ctypedef packed struct WEDLogTimestamp:
        uint8_t type
        uint32_t timestamp
        uint8_t flags

    ctypedef packed struct WEDLogAccel:
        uint8_t type
        int8_t accel[3]

    ctypedef packed struct WEDLogAccelCmp:
        uint8_t type
        uint8_t count_bits
        uint8_t data[0]

    ctypedef packed struct WEDLogLSConfig:
        uint8_t type
        uint8_t dac_on
        uint8_t flags
        uint8_t level_led
        uint8_t gain
        uint8_t log_size

    ctypedef packed struct WEDLogLSData:
        uint8_t type
        uint16_t val[3]

    ctypedef packed struct WEDLogTemp:
        uint8_t type
        int16_t temperature

    cdef enum:
        WED_TAG_SIZE = 4
        WED_TAG_BITS = 0x1F

    ctypedef packed struct WEDLogTag:
        uint8_t type
        uint32_t tag[WED_TAG_SIZE]

    ctypedef packed struct WEDLogCount:
        uint8_t type
        uint32_t log_timestamp
        uint16_t log_accel_count
        uint32_t old_timestamp
        uint32_t timestamp

    ctypedef packed struct WEDLogEvent:
        uint8_t type
        uint8_t flags

    int get_packet_len(const char * pPayload)
