
#include "sensor_parse.h"

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
