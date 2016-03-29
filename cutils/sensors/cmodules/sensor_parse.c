
#include <errno.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "sensor_parse.h"

/******************************************************************************/
typedef struct _get_bits {
    const uint8 * buf;
    unsigned int pos;
    unsigned int field_count;
} get_bits_t;


/******************************************************************************/
static inline void cmpGetBitsInit(get_bits_t * gb, const uint8 * buf) {

    gb->buf = buf;
    gb->pos = 0;
}
/******************************************************************************/
static int8 cmpGetBits(get_bits_t * gb, uint8 nbits)
{

    int8 val = gb->buf[0] << gb->pos;

    uint8 buf0bits = 8 - gb->pos;
    if (buf0bits < nbits)
        val |= gb->buf[1] >> buf0bits;

    gb->pos += nbits;
    if (gb->pos >= 8) {
        gb->buf++;
        gb->pos -= 8;
    }

    return val >> (8 - nbits);
}
/******************************************************************************/
int get_cmp_nbits(uint8 count_bits)
{
    int nbits = -1;
    nbits = -1;
    switch ((count_bits & 0x70) >> 4) {
    case WED_LOG_ACCEL_CMP_3_BIT:
        nbits = 3;
        break;
    case WED_LOG_ACCEL_CMP_4_BIT:
        nbits = 4;
        break;
    case WED_LOG_ACCEL_CMP_5_BIT:
        nbits = 5;
        break;
    case WED_LOG_ACCEL_CMP_6_BIT:
        nbits = 6;
        break;
    case WED_LOG_ACCEL_CMP_8_BIT:
        nbits = 8;
        break;
    case WED_LOG_ACCEL_CMP_STILL:
        if (count_bits & 0x80)
            nbits = 0;
        break;
    default:
        break;
    }
    return nbits;
}
/******************************************************************************/
int stream_len(const char * pInBuf, int * pnInLen, int * pnOutLen, const cmp_state_t * pState)
{
    int err = 0;
    if (pInBuf == NULL || pnInLen == NULL || pnOutLen == NULL || pState == NULL)
        return AMERR_INVALID_PARAM;
    if (*pnInLen <= 0) {
        *pnInLen = 0;
        *pnOutLen = 0;
        return AMERR_INVALID_PARAM;
    }
    WEDLogAccelCmp logAccelCmp;
    uint8_t field_count;
    int nbits;

    int bValid = pState->accel.bValid;
    int buflen = *pnInLen;
    int payload = 0;
    int copied = 0;
    while (payload < buflen) {
        WED_LOG_TYPE log_type = pInBuf[payload] & 0x0F;
        int packet_len = get_packet_len(&pInBuf[payload]);
        if (packet_len <= 0) {
            err = AMERR_INVALID_PACKET;
            break;
        }
        if ((packet_len + payload) > buflen) {
            break;
        }
        switch (log_type) {
        default:
            copied += packet_len;
            break;
        case WED_LOG_ACCEL:
            bValid = 1;
            copied += packet_len;
            break;
        case WED_LOG_ACCEL_CMP:
            logAccelCmp.type = log_type;
            logAccelCmp.count_bits = pInBuf[payload + 1];
            field_count = (logAccelCmp.count_bits & 0xF) + 1;
            nbits = get_cmp_nbits(logAccelCmp.count_bits);

            if (nbits < 0) {
                err = AMERR_INVALID_CMP_PACKET;
                break;
            }

            if (nbits == 8)
                bValid = 1;

            if (!bValid)
                break;

            copied += field_count * sizeof(WEDLogAccel);
            break;
        } // end switch (log_type

        payload += packet_len;
    } // end while(payload <

    if (!err && *pnInLen != payload)
        err = AMERR_UNPROCESED_INPUT;

    *pnInLen = payload;
    *pnOutLen = copied;
    return err;
}
/******************************************************************************/
uint8 cmpNbits(int16 diff)
{

    uint8 v = (diff < 0) ? ~diff : diff;
    uint8 nbits = 1;
    while (v) {
        nbits++;
        v >>= 1;
    }
    return nbits;
}
/******************************************************************************/
int8 decode_accel(int8 old_accel, int8 diff, uint8 nbits)
{
    int8 accel = old_accel + diff; // Yes this may result in integer overflow!
    int16 diff16 = accel - old_accel;
    uint8 enc_nbits = cmpNbits(diff16);
    if (enc_nbits > nbits) {
        // some packet must be lost! try to recover
        if (enc_nbits > 6) {
            if (old_accel < 0 && diff < 0)
                accel = -128;
            else if (old_accel > 0 && diff > 0)
                accel = 127;
        } else {
            accel = old_accel;
        }
    }

    return accel;
}
/******************************************************************************/
int stream_decompress(const char * pInBuf, int * pnInLen, char * pOutBuf, int * pnOutLen, cmp_state_t * pState)
{
    int err = 0;
    if (pInBuf == NULL || pnInLen == NULL || pOutBuf == NULL || pnOutLen == NULL || pState == NULL)
        return AMERR_INVALID_PARAM;
    if (*pnInLen <= 0 || *pnOutLen <= 0) {
        *pnInLen = 0;
        *pnOutLen = 0;
        return 0;
    }
    WEDLogAccelCmp logAccelCmp;
    uint8_t field_count;
    const uint8_t * pdu;
    int nbits;

    amiigo_accel_t * pAccel = &pState->accel;
    WEDLogAccel logAccel = {WED_LOG_ACCEL, {pAccel->accel[0],pAccel->accel[1],pAccel->accel[2]}};
    int i;
    int buflen = *pnInLen;
    int nOutLen = *pnOutLen;
    int payload = 0;
    int copied = 0;
    while (payload < buflen) {
        WED_LOG_TYPE log_type = pInBuf[payload] & 0x0F;
        int packet_len = get_packet_len(&pInBuf[payload]);
        if (packet_len <= 0) {
            err = AMERR_INVALID_PACKET;
            break;
        }
        if ((packet_len + payload) > buflen ||
                (copied + packet_len) > nOutLen) {
            break;
        }
        int no_room = 0;
        switch (log_type) {
        default:
            memcpy(&pOutBuf[copied], &pInBuf[payload], packet_len);
            copied += packet_len;
            break;
        case WED_LOG_ACCEL:
            pAccel->bValid = 1;
            for (i = 0; i < 3; ++i)
                logAccel.accel[i] = pInBuf[payload + 1 + i];
            memcpy(&pOutBuf[copied], &pInBuf[payload], packet_len);
            copied += packet_len;
            break;
        case WED_LOG_ACCEL_CMP:
            logAccelCmp.type = log_type;
            logAccelCmp.count_bits = pInBuf[payload + 1];
            field_count = (logAccelCmp.count_bits & 0xF) + 1;
            nbits = get_cmp_nbits(logAccelCmp.count_bits);

            if (nbits < 0) {
                err = AMERR_INVALID_CMP_PACKET;
                break;
            }

            if (nbits == 8)
                pAccel->bValid = 1;

            if (!pAccel->bValid) {
                pState->ignored_cmp_count++;
                break;
            }

            if (copied + field_count * sizeof(WEDLogAccel) > nOutLen) {
                no_room = 1;
                break;
            }
            if (nbits == 0) {
                while (field_count--) {
                    memcpy(&pOutBuf[copied], &logAccel, sizeof(logAccel));
                    copied += sizeof(WEDLogAccel);
                }
                break;
            }
            pdu = (const uint8 *)&pInBuf[payload];
            pdu += 2;

            if (nbits == 8) {
                while (field_count--) {
                    for (i = 0; i < 3; ++i)
                        logAccel.accel[i] = pdu[i];
                    pdu += 3;
                    memcpy(&pOutBuf[copied], &logAccel, sizeof(logAccel));
                    copied += sizeof(WEDLogAccel);
                }
            } else {
                get_bits_t gb;
                cmpGetBitsInit(&gb, pdu);
                while (field_count--) {
                    uint8 i;
                    for (i = 0; i < 3; i++) {
                        int8 diff = cmpGetBits(&gb, nbits);
                        logAccel.accel[i] = decode_accel(logAccel.accel[i], diff, nbits);
                    }
                    memcpy(&pOutBuf[copied], &logAccel, sizeof(logAccel));
                    copied += sizeof(WEDLogAccel);
                }
            }
            break;
        } // end switch (log_type

        if (no_room)
            break;

        payload += packet_len;

    } // end while(payload <

    for (i = 0; i < 3; ++i)
        pAccel->accel[i] = logAccel.accel[i];

    *pnInLen = payload;
    *pnOutLen = copied;
    return err;
}
/******************************************************************************/
int get_packet_len(const char * pPayload) {
    WED_LOG_TYPE log_type = pPayload[0] & WED_TAG_BITS;
    int packet_len = -1;
    switch (log_type) {
    case WED_LOG_TIME:
        packet_len = sizeof(WEDLogTimestamp);
        break;
    case WED_LOG_ACCEL:
        packet_len = sizeof(WEDLogAccel);
        break;
    case WED_LOG_LS_CONFIG:
        packet_len = sizeof(WEDLogLSConfig);
        break;
    case WED_LOG_LS_DATA:
        packet_len = WEDLogLSDataSize((void *)pPayload);
        break;
    case WED_LOG_TEMP:
        packet_len = sizeof(WEDLogTemp);
        break;
    case WED_LOG_TAG:
        packet_len = sizeof(WEDLogTag);
        break;
    case WED_LOG_ACCEL_CMP:
        packet_len = WEDLogAccelCmpSize((void *)pPayload);
        break;
    case WED_LOG_COUNT:
        packet_len = sizeof(WEDLogCount);
        break;
    case WED_LOG_EVENT:
        packet_len = sizeof(WEDLogEvent);
        break;
    default:
        break;
    }

    return packet_len;
}

int get_compressed_log_count(const char * pPayload) {
    WED_LOG_TYPE log_type = pPayload[0] & WED_TAG_BITS;
    if (log_type != WED_LOG_ACCEL_CMP)
        return 0;
    return (((uint8) pPayload[1]) & 0xF) + 1;
}

