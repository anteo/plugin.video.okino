# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))

import datetime
from okino.common import sleep, abort_requested
from okino.library import update_library
from okino.plugin import plugin
from xbmcswift2 import xbmc
import okino.plugin.main


def safe_update():
    try:
        update_library()
        plugin.close_storages()
    except Exception as e:
        plugin.log.exception(e)

if __name__ == '__main__':
    sleep(5000)
    safe_update()
    next_run = None
    while not abort_requested():
        now = datetime.datetime.now()
        if not next_run:
            next_run = now
            next_run += datetime.timedelta(hours=12)
            plugin.log.info("Scheduling next library update at %s" % next_run)
        elif now > next_run:
            if not xbmc.Player().isPlaying():
                safe_update()
                next_run = None
        sleep(1000*60)
