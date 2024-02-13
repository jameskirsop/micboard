import time
import logging
import select
import queue

from networkdevice import SennheiserNetworkDevice, SENN_PORT
from channel import chart_update_list, data_update_list
import socket

NetworkDevices = []
DeviceMessageQueue = queue.Queue()

def get_network_device_by_ip(ip):
    return next((x for x in NetworkDevices if x.ip == ip), None)

def check_add_network_device(ip, type):
    net = get_network_device_by_ip(ip)
    if net:
        return net

    net = SennheiserNetworkDevice(ip, type)
    NetworkDevices.append(net)
    print('Network Device list')
    # print(NetworkDevices)
    # print(net.rx_com_status)
    # print(net.type)
    return net

def watchdog_monitor():
    for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED'):
        if (int(time.perf_counter()) - rx.socket_watchdog) > 7:
            logging.debug('disconnected from: %s', rx.ip)
            rx.socket_disconnect()

    for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTING'):
        if (int(time.perf_counter()) - rx.socket_watchdog) > 4:
            print(f"{rx.ip} is about to disconnect")
            rx.socket_disconnect()


    for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'DISCONNECTED'):
        if (int(time.perf_counter()) - rx.socket_watchdog) > 20:
            print('%s is attempting to reconnect' % rx.ip)
            rx.socket_connect()

def ProcessRXMessageQueue():
    while True:
        rx, msg = DeviceMessageQueue.get()
        rx.parse_raw_rx(msg)

def SocketService():
    # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # try:
    #     sock.bind(('',SENN_PORT))
    # except socket.error:
    #     print('ERRRRRRRRRRRRORRRRRRRRRRRRRR')
    for rx in NetworkDevices:
        rx.socket_connect()

    while True:
        # logging.debug('Running watchdog')
        watchdog_monitor()
        readrx = [rx for rx in NetworkDevices if rx.rx_com_status in ['CONNECTING', 'CONNECTED']]
        writerx = [rx for rx in readrx if not rx.writeQueue.empty()]

        read_socks, write_socks, error_socks = select.select(readrx, writerx, readrx, .2)

        for rx in read_socks:
            try:
                # data,ip = sock.recvfrom(1024)
                data,ip = rx.f.recvfrom(1024)
                # print(ip, rx)
                # print(NetworkDevices)
                sendingUnit = list(filter(lambda x: x.ip == ip[0], NetworkDevices))[0]
            except:
                logging.debug('read socks exception')
                sendingUnit.socket_disconnect()
                break
            
            # print(ip)
            # for rx in NetworkDevices:
            #     if rx.ip == ip:
            DeviceMessageQueue.put((sendingUnit, data))
            logging.debug('SETTING CONNECTED')
            sendingUnit.socket_watchdog = int(time.perf_counter())
            sendingUnit.set_rx_com_status('CONNECTED')
            if int(time.perf_counter()) - sendingUnit.metering_start > 58:
                sendingUnit.enable_metering(.5)



        for rx in write_socks:
            string = rx.writeQueue.get()
            logging.debug("write: %s data: %s", rx.ip, string)
            try:
                rx.f.sendto(bytes(string+'\r', 'ascii'), (rx.ip, SENN_PORT))
            except:
                logging.warning("TX ERROR IP: %s String: %s", rx.ip, string)


        for rx in error_socks:
            logging.debug('error socks!')
            rx.set_rx_com_status('DISCONNECTED')