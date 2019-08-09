"""Voco adapter and notifier for Mozilla WebThings Gateway."""

from os import path
import functools
import gateway_addon
import signal
import sys
import time

import threading
import queue

sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

from pkg.voco_adapter import VocoAdapter  # noqa
from pkg.voco_notifier import VocoNotifier  # noqa
#from pkg.voco_parent import VocoParent  # noqa

_API_VERSION = {
    'min': 2,
    'max': 2,
}
_ADAPTER = None
_ADAPTER2 = None



print = functools.partial(print, flush=True)


def cleanup(signum, frame):
    """Clean up any resources before exiting."""
    if _ADAPTER is not None:
        _ADAPTER.close_proxy()
    if _ADAPTER2 is not None:
        _ADAPTER2.close_proxy()
    sys.exit(0)



def notifier_thread(shared_object):
    print("starting notifier as thread")
    _ADAPTER2 = VocoNotifier(shared_object,verbose=True)
    print("-")
    print("started notifier")

if __name__ == '__main__':
    if gateway_addon.API_VERSION < _API_VERSION['min'] or \
            gateway_addon.API_VERSION > _API_VERSION['max']:
        print('Unsupported API version.')
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    voice_messages_queue = queue.Queue()

    #shared_object = VocoParent('grandpa')

    # Start the internal clock which is used to handle timers.
    print("-")
    print("starting thread")
    th = threading.Thread(target=notifier_thread, args=(voice_messages_queue,))
    th.daemon = True
    th.start()

    print("-")
    print("starting adapter")
    _ADAPTER = VocoAdapter(voice_messages_queue,verbose=True)
    print("-")
    print("started adapter")
    #_ADAPTER2 = VocoNotifier(shared_object,verbose=True)
    #print("-")
    #print("started notifier")
    # Wait until the proxy stops running, indicating that the gateway shut us
    # down.
    while _ADAPTER.proxy_running(): # and _ADAPTER2.proxy_running()
        time.sleep(2)
