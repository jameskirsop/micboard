import time
import queue
import socket
from collections import defaultdict
import logging

from device_config import BASE_CONST
from iem import IEM
from mic import WirelessMic
from mic import SennheiserWirelessMic


PORT = 2202
SENN_PORT = 53212

class NetworkDevice:
    def __init__(self, ip, type):
        self.ip = ip
        self.type = type
        self.f = None
        self.rx_com_status = 'DISCONNECTED'
        self.writeQueue = queue.Queue()
        self.channels = []
        self.socket_watchdog = int(time.perf_counter())
        self.raw = defaultdict(dict)
        self.BASECONST = BASE_CONST[self.type]['base_const']

    def add_channel_device(self, cfg):
        if BASE_CONST[self.type]['DEVICE_CLASS'] == 'WirelessMic':
            self.channels.append(WirelessMic(self, cfg))
        if BASE_CONST[self.type]['DEVICE_CLASS'] == 'SennheiserWirelessMic':
            self.channels.append(SennheiserWirelessMic(self, cfg))
        elif BASE_CONST[self.type]['DEVICE_CLASS'] == 'IEM':
            self.channels.append(IEM(self, cfg))

    def socket_disconnect(self):
        self.f.close()
        self.set_rx_com_status('DISCONNECTED')
        self.socket_watchdog = int(time.perf_counter())

    def net_json(self):
        ch_data = []
        for channel in self.channels:
            data = channel.ch_json()
            if self.rx_com_status == 'DISCONNECTED':
                data['status'] = 'RX_COM_ERROR'
            ch_data.append(data)
        data = {
            'ip': self.ip, 'type': self.type, 'status': self.rx_com_status,
            'raw': self.raw, 'tx': ch_data
        }
        return data

    def fileno(self):
        return self.f.fileno()

    def get_all(self):
        ret = []
        for channel in self.get_channels():
            for s in self.BASECONST['getAll']:
                ret.append(s.format(channel))

        return ret

    def get_channels(self):
        channels = []
        for channel in self.channels:
            channels.append(channel.channel)
        return channels

    def set_rx_com_status(self, status):
        self.rx_com_status = status
        # if status == 'CONNECTED':
        #     print("Connected to {} at {}".format(self.ip,datetime.datetime.now()))
        # elif status == 'DISCONNECTED':
        #     print("Disconnected from {} at {}".format(self.ip,datetime.datetime.now()))


class ShureNetworkDevice(NetworkDevice):
    def __init__(self, ip, type):
        NetworkDevice.__init__(self, ip, type)
        self.ip = ip
        self.type = type
        self.channels = []
        self.rx_com_status = 'DISCONNECTED'
        self.writeQueue = queue.Queue()
        self.f = None
        self.raw = defaultdict(dict)

    def socket_connect(self):
        try:
            if BASE_CONST[self.type]['PROTOCOL'] == 'TCP':
                self.f = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP
                self.f.settimeout(.2)
                self.f.connect((self.ip, PORT))


            elif BASE_CONST[self.type]['PROTOCOL'] == 'UDP':
                self.f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #UDP

            self.set_rx_com_status('CONNECTING')
            self.enable_metering(.1)

            for string in self.get_all():
                self.writeQueue.put(string)
        except socket.error as e:
            self.set_rx_com_status('DISCONNECTED')

        self.socket_watchdog = int(time.perf_counter())

    def get_device_by_channel(self, channel):
        return next((x for x in self.channels if x.channel == int(channel)), None)

    def parse_raw_rx(self, data):
        data = data.strip('< >').strip('* ')
        data = data.replace('{', '').replace('}', '')
        data = data.rstrip()
        split = data.split()
        if data:
            try:
                if split[0] in ['REP', 'REPORT', 'SAMPLE'] and split[1] in ['1', '2', '3', '4']:
                    ch = self.get_device_by_channel(int(split[1]))
                    ch.parse_raw_ch(data)

                elif split[0] in ['REP', 'REPORT']:
                    self.raw[split[1]] = ' '.join(split[2:])
            except:
                logging.warning("Index Error(RX): %s", data)

    def get_query_strings(self):
        ret = []
        for channel in self.get_channels():
            for s in self.BASECONST['query']:
                ret.append(s.format(channel))

        return ret


    def enable_metering(self, interval):
        if self.type in ['qlxd', 'ulxd', 'axtd', 'p10t']:
            for i in self.get_channels():
                self.writeQueue.put('< SET {} METER_RATE {:05d} >'.format(i, int(interval * 1000)))
        elif self.type == 'uhfr':
            for i in self.get_channels():
                self.writeQueue.put('* METER {} ALL {:03d} *'.format(i, int(interval/30 * 1000)))

    def disable_metering(self):
        for i in self.get_channels():
            self.writeQueue.put(self.BASECONST['meter_stop'].format(i))


# self.f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# self.f.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# self.f.bind(('',SENN_PORT))


class SennheiserNetworkDevice(NetworkDevice):
    def __init__(self, ip, type):
        NetworkDevice.__init__(self, ip, type)
        self.metering_start = int(time.perf_counter())

    def socket_connect(self):
        # self.set_rx_com_status('DISCONNECTED')
        # return
        try:
            # self.f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.f.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.f.bind(('',SENN_PORT))
            # self.f.settimeout(.2)
            # self.f.connect((self.ip, SENN_PORT))
            self.set_rx_com_status('CONNECTING')
            for string in self.get_all():
                self.writeQueue.put(string)
            
            self.enable_metering(.5)

        except socket.error as e:
            print(e)
            self.set_rx_com_status('DISCONNECTED')

        print('Printing at socket_connect')
        self.socket_watchdog = int(time.perf_counter())

    # Right now we're only supporting one channel per Sennheiser device...
    def get_device_by_channel(self, channel):
        return self.channels[0]
        # return next((x for x in self.channels if x.channel == int(channel)), None)

    def enable_metering(self, interval):
        for i in self.get_channels():
            self.writeQueue.put('Push 60 %d 1' % (int(interval * 1000)))
            self.metering_start = int(time.perf_counter())
            # self.writeQueue.put('Push 0 100 0'.format(int(interval * 1000)))
            # self.writeQueue.put('Push 0 100 0')

    def disable_metering(self):
        for i in self.get_channels():
            self.writeQueue.put(self.BASECONST['meter_stop'].format(i))

    def parse_raw_rx(self, data):
        split = data.decode('UTF-8').split('\r')
        if split[0] == 'Push 0 0 1':
            print('Config Details')
            # print(split)
            # ch = self.get_device_by_channel(1)
            # print(type(ch))
            # ch.parse_raw_ch(data)
        elif split[0] == 'Push 0 100 0':
            print('Cyclic Attributes')
            # ch = self.get_device_by_channel(1)
            # print(type(ch))
            # ch.parse_raw_ch(data)
        ch = self.get_device_by_channel(1)
        ch.parse_raw_ch(data)
        # data = data.strip('< >').strip('* ')
        # data = data.replace('{', '').replace('}', '')
        # data = data.rstrip()
        # split = data.split()
        # if data:
        #     try:
        #         if split[0] in ['REP', 'REPORT', 'SAMPLE'] and split[1] in ['1', '2', '3', '4']:
        #             ch = self.get_device_by_channel(int(split[1]))
        #             ch.parse_raw_ch(data)

        #         elif split[0] in ['REP', 'REPORT']:
        #             self.raw[split[1]] = ' '.join(split[2:])
        #     except:
        #         logging.warning("Index Error(RX): %s", data)
