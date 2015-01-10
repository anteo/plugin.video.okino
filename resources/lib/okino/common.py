# -*- coding: utf-8 -*-

import time
import os
import sys

from util.causedexception import CausedException
from util.enum import Enum
from util.ordereddict import OrderedDict
from xbmcswift2 import CLI_MODE, xbmc
from plugin import plugin


ADDON_PATH = plugin.addon.getAddonInfo('path')
RESOURCES_PATH = os.path.join(ADDON_PATH, 'resources')
lang = plugin.get_string


def notify(message, delay=5000):
    plugin.notify(message, lang(30000), delay, plugin.addon.getAddonInfo('icon'))


def abort_requested():
    if CLI_MODE:
        return False
    else:
        return xbmc.abortRequested


def sleep(ms):
    if CLI_MODE:
        time.sleep(ms/1000.0)
    else:
        xbmc.sleep(ms)


def filter_dict(d):
    return dict((data for data in d.iteritems() if data[1] is not None))


def validate_save_path(path):
    if "://" in path:
        if sys.platform.startswith('win') and path.lower().startswith("smb://"):
            path = path.replace("smb:", "").replace("/", "\\")
        else:
            raise LocalizedError(33030, "Downloading to an unmounted network share is not supported",
                                 check_settings=True)
    if not os.path.isdir(path):
        raise LocalizedError(33030, "Download path doesn't exist", check_settings=True)
    return path


def str_to_date(date_string, date_format='%d.%m.%Y'):
    """
    Instead of calling datetime.strptime directly, we need this hack because of Exception raised on second XBMC run,
    See: http://forum.kodi.tv/showthread.php?tid=112916
    """
    import datetime
    import time
    return datetime.date(*(time.strptime(date_string, date_format)[0:3]))


def date_to_str(date, date_format='%d.%m.%Y'):
    return date.strftime(date_format)


def singleton(func):
    memoized = []

    def singleton_wrapper(*args, **kwargs):
        if args or kwargs:
            raise TypeError("Singleton-wrapped functions shouldn't take"
                            "any argument! (%s)" % func)
        if not memoized:
            memoized.append(func())
        return memoized[0]

    return singleton_wrapper


def batch(iterable, size=None):
    from itertools import islice, chain
    size = size or plugin.get_setting('batch-results', int)
    sourceiter = iter(iterable)
    while True:
        batchiter = islice(sourceiter, size)
        yield list(chain([batchiter.next()], batchiter))


class LocalizedEnum(Enum):
    @property
    def lang_id(self):
        raise NotImplementedError()

    @property
    def localized(self):
        return self.localized_title if hasattr(self, 'localized_title') \
            else lang(self.lang_id)

    @classmethod
    def strings(cls):
        d = [(i.name, i.localized(lang)) for i in cls if i.lang_id >= 0]
        return OrderedDict(sorted(d, key=lambda t: t[1]))

    def __lt__(self, other):
        return self.localized < other.localized


class LocalizedError(CausedException):
    def __init__(self, lang_code, reason, *args, **kwargs):
        CausedException.__init__(self, **kwargs)
        self.reason = reason
        self.reason_args = args
        self.lang_code = lang_code

    @property
    def localized(self):
        return lang(self.lang_code) % self.reason_args

    def __str__(self):
        if isinstance(self.reason, basestring):
            return self.reason % self.reason_args
        else:
            return str(self.reason)
