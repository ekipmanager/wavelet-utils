
#ifndef SENSOR_PARSE_H
#define SENSOR_PARSE_H

#if defined(__GNUC__) || defined(__clang__)
#ifndef TRUE
#define TRUE 1
#endif

#ifndef FALSE
#define FALSE 0
#endif
#include <stdint.h>

typedef int8_t int8;
typedef uint8_t uint8;
typedef int16_t int16;
typedef uint16_t uint16;
typedef int32_t int32;
typedef uint32_t uint32;
#if defined(__GNUC__)
#include <stdbool.h>
#endif
#  define PACKED __attribute__((__packed__))
#else
#  define PACKED
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define WED_TAG_SIZE 4
#define WED_TAG_BITS 0x1F


#define AMERR_INVALID_PARAM          -2 // Invalid input parameter
#define AMERR_UNPROCESED_INPUT       -3 // Some input not processed due to error
#define AMERR_INVALID_PACKET         -4 // Invalid or unknown packet
#define AMERR_INVALID_CMP_PACKET     -5 // Invalid compressed packet


typedef enum {
    WED_LOG_TIME,
    WED_LOG_ACCEL,
    WED_LOG_LS_CONFIG,
    WED_LOG_LS_DATA,
    WED_LOG_TEMP,
    WED_LOG_TAG,
    WED_LOG_ACCEL_CMP,
    WED_LOG_COUNT,
    WED_LOG_EVENT,
} WED_LOG_TYPE;


typedef struct {
    uint8 type; // WED_LOG_TIME
    uint32 timestamp;
    uint8 flags;
} PACKED WEDLogTimestamp;

typedef struct {
    uint8 type; // WED_LOG_ACCEL
    int8 accel[3];
} PACKED WEDLogAccel;

enum {
    WED_LOG_ACCEL_CMP_3_BIT,
    WED_LOG_ACCEL_CMP_4_BIT,
    WED_LOG_ACCEL_CMP_5_BIT,
    WED_LOG_ACCEL_CMP_6_BIT,
    WED_LOG_ACCEL_CMP_8_BIT,
    WED_LOG_ACCEL_CMP_STILL,
};

typedef struct {
    uint8 type;
    uint8 count_bits;
    uint8 data[0];
} PACKED WEDLogAccelCmp;

static inline uint8 WEDLogAccelCmpSize(void* buf) {

    WEDLogAccelCmp* pkt = buf;

    uint8 bps = 8;
    switch ((pkt->count_bits >> 4) & 0x7) {
    case WED_LOG_ACCEL_CMP_3_BIT: bps = 3*3; break;
    case WED_LOG_ACCEL_CMP_4_BIT: bps = 4*3; break;
    case WED_LOG_ACCEL_CMP_5_BIT: bps = 5*3; break;
    case WED_LOG_ACCEL_CMP_6_BIT: bps = 6*3; break;
    case WED_LOG_ACCEL_CMP_8_BIT: bps = 8*3; break;
    case WED_LOG_ACCEL_CMP_STILL: return 2;
    }

    uint16 bits = ((pkt->count_bits & 0xf) + 1) * bps;
    if (bits > 144)
        return 0;

    return 2 + ((uint8)bits - 1) / 8 + 1;
}

typedef struct {
    uint8 type; // WED_LOG_LS_CONFIG
    uint8 dac_on;
    uint8 flags;
    uint8 level_led;
    uint8 gain;
    uint8 log_size;
} PACKED WEDLogLSConfig;

typedef struct {
    uint8 type; // WED_LOG_LS_DATA
    uint16 val[3];
} PACKED WEDLogLSData;

static inline uint8 WEDLogLSDataSize(void* buf) {
    return sizeof(uint8) + (sizeof(uint16) * (
        ((((WEDLogLSData*)buf)->type & 0x80) ? 1 : 0) +
        ((((WEDLogLSData*)buf)->type & 0x40) ? 1 : 0) +
        ((((WEDLogLSData*)buf)->type & 0x20) ? 1 : 0)
        ));
}

typedef struct {
    uint8 type; // WED_LOG_TEMP
    int16 temperature;  // DegC * 10
} PACKED WEDLogTemp;


typedef struct {
    uint8 type; // WED_LOG_TAG
    uint8 tag[WED_TAG_SIZE];
} PACKED WEDLogTag;


typedef struct {
    uint8 type; // WED_LOG_COUNT
    uint32 log_timestamp;
    uint16 log_accel_count;
    uint32 old_timestamp;
    uint32 timestamp;
} PACKED WEDLogCount;

typedef struct {
    uint8 type;     // WED_LOG_EVENT
    uint8 flags;
} PACKED WEDLogEvent;

typedef struct _amiigo_accel {
    int bValid;
    int accel[3];
} amiigo_accel_t;

typedef struct _cmp_state {
    amiigo_accel_t accel;
    unsigned int ignored_cmp_count;
} cmp_state_t;


#ifdef __cplusplus
}
#endif

int get_packet_len(const char * pPayload);

int get_compressed_log_count(const char * pPayload);

int stream_decompress(const char * pInBuf, int * pnInLen, char * pOutBuf, int * pnOutLen, cmp_state_t * pState);

int stream_len(const char * pInBuf, int * pnInLen, int * pnOutLen, const cmp_state_t * pState);

#endif // include guard
