import threading
import time


import config
import tornado_server
import shure
import sennheiser
import discover
import discover_sennheiser


def main():
    config.config()

    time.sleep(.1)
    rxcom_t = threading.Thread(target=shure.SocketService)
    rxcom_senn_t = threading.Thread(target=sennheiser.SocketService)
    rxquery_t = threading.Thread(target=shure.WirelessQueryQueue)
    web_t = threading.Thread(target=tornado_server.twisted)
    discover_t = threading.Thread(target=discover.discover)
    discover_sennheiser_t = threading.Thread(target=discover_sennheiser.discover)
    rxparse_t = threading.Thread(target=shure.ProcessRXMessageQueue)
    rxparse__sennheiser_t = threading.Thread(target=sennheiser.ProcessRXMessageQueue)

    rxquery_t.start()
    rxcom_t.start()
    rxcom_senn_t.start()
    web_t.start()
    discover_t.start()
    discover_sennheiser_t.start()
    rxparse_t.start()
    rxparse__sennheiser_t.start()


if __name__ == '__main__':
    main()
