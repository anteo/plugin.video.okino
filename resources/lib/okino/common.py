# -*- coding: utf-8 -*-

import time
import os
import sys
import shutil
import logging
import threading

from util.causedexception import CausedException
from util.enum import Enum
from util.ordereddict import OrderedDict
from xbmcswift2 import CLI_MODE, xbmc, xbmcvfs, xbmcgui
from contextlib import closing
from plugin import plugin


ADDON_PATH = plugin.addon.getAddonInfo('path')
RESOURCES_PATH = os.path.join(ADDON_PATH, 'resources')
lang = plugin.get_string
log = logging.getLogger(__name__)


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


def save_path(local=False):
    path = plugin.get_setting('save-path', unicode)
    if path == plugin.get_setting('temp-path', unicode):
        raise LocalizedError(33032, "Path for downloaded files and temporary path should not be the same",
                             check_settings=True)
    if not xbmcvfs.exists(path):
        raise LocalizedError(33031, "Invalid save path", check_settings=True)
    if local:
        path = ensure_path_local(path)
    return path


def ensure_path_local(path):
    path = xbmc.translatePath(path)
    if "://" in path:
        if sys.platform.startswith('win') and path.lower().startswith("smb://"):
            path = path.replace("smb:", "").replace("/", "\\")
        else:
            raise LocalizedError(33030, "Downloading to an unmounted network share is not supported",
                                 check_settings=True)
    return path


def temp_path():
    path = ensure_path_local(plugin.get_setting('temp-path', unicode))
    if not os.path.isdir(path):
        try:
            os.mkdir(path)
        except OSError:
            raise LocalizedError(33030, "Invalid temporary path", check_settings=True)
    return path


class FileCopyingThread(threading.Thread):
    def __init__(self, src, dst, delete=False):
        super(FileCopyingThread, self).__init__()
        self.src = src
        self.dst = dst
        self.delete = delete
        self.tmp = self.dst + ".part"
        self.src_size = self._file_size(self.src)

    @staticmethod
    def _file_size(path):
        with closing(xbmcvfs.File(path)) as f:
            return f and f.size() or 0

    def run(self):
        log.info("Copying %s to %s...", self.src, self.dst)
        if xbmcvfs.exists(self.dst):
            xbmcvfs.delete(self.dst)
        xbmcvfs.mkdirs(os.path.dirname(self.dst))
        if xbmcvfs.copy(self.src, self.tmp):
            log.info("Success.")
            if xbmcvfs.rename(self.tmp, self.dst):
                if self.delete and xbmcvfs.delete(self.src):
                    log.info("File %s deleted.", self.src)
            else:
                log.info("Renaming %s to %s failed.", self.tmp, self.dst)
                xbmcvfs.delete(self.tmp)
        else:
            log.info("Failed.")

    def progress(self):
        cur_size = self._file_size(self.tmp)
        return self.src_size and cur_size*100/self.src_size or 0


class FileCopyThread(threading.Thread):
    def __init__(self, src, dst, delete=False):
        super(FileCopyThread, self).__init__()
        self.src = src
        self.dst = dst
        self.delete = delete

    def run(self):
        progress = xbmcgui.DialogProgressBG()
        with closing(progress):
            progress.create(lang(40319), os.path.basename(self.src))
            copying_thread = FileCopyingThread(self.src, self.dst, self.delete)
            copying_thread.start()
            while copying_thread.is_alive():
                xbmc.sleep(250)
                progress.update(copying_thread.progress())


def copy_file(src, dst, delete=False):
    copying_thread = FileCopyThread(src, dst, delete)
    copying_thread.start()


def save_files(files, rename=False):
    save = plugin.get_setting('save-files', int)
    if not save:
        return
    src, dst = temp_path(), save_path()
    files_dict = {}
    for old_path in files:
        rel_path = os.path.relpath(old_path, src)
        new_path = os.path.join(dst, rel_path)
        if xbmcvfs.exists(new_path):
            if rename:
                if xbmcvfs.delete(old_path):
                    log.info("File %s deleted.", old_path)
            continue
        files_dict[old_path] = new_path
    if not files_dict:
        return
    if save != 2 or xbmcgui.Dialog().yesno(lang(30000), *lang(40318).split("|")):
        for n, old_path in enumerate(files):
            if old_path not in files_dict:
                continue
            new_path = files_dict[old_path]
            xbmcvfs.mkdirs(os.path.dirname(new_path))
            if rename:
                log.info("Renaming %s to %s...", old_path, new_path)
                if not xbmcvfs.rename(old_path, new_path):
                    log.info("Renaming failed. Trying to copy and delete old file...")
                    copy_file(old_path, new_path, delete=True)
                else:
                    log.info("Success.")
            else:
                copy_file(old_path, new_path)


def get_dir_size(directory):
    dir_size = 0
    for (path, dirs, files) in os.walk(directory):
        for f in files:
            filename = os.path.join(path, f)
            dir_size += os.path.getsize(filename)
    return dir_size


def purge_temp_dir():
    path = temp_path()
    temp_size = get_dir_size(path)
    max_size = plugin.get_setting('temp-max-size', int)*1024*1024*1024
    if temp_size > max_size:
        shutil.rmtree(path, True)
        if not os.path.isdir(path):
            os.mkdir(path)


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
