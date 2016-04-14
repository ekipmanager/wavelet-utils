

class Commands:
    STATUS = 0
    BLINK = 1
    DOWNLOAD = 2


class AmiigoSettings:
    def __init__(self):
        # BLE handles
        self.status_handle = 0x0025
        self.config_handle = 0x0027

        # packet formats
        self.download_pattern = '=BB'
        self.status_pattern = '=IBBIIB'
        self.config_pattern = '=HHHHHHHBBB'
        self.blink_pattern = '=BBBBB'

        self.mode_names = {0: "Slow",
                           1: "Fast",
                           2: "Sleep"}
